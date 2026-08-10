"""Corrections Studio revisioned command/ack protocol (Theme C Phase 6)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Optional

PROTOCOL_VERSION = "1"

CorrectionsActionName = Literal[
    "select_candidate",
    "accept",
    "reject",
    "skip",
    "edit_draft",
    "generate",
    "preview",
    "apply_export",
]

CorrectionsAckStatus = Literal[
    "ok",
    "rejected_stale",
    "rejected_protocol",
    "error",
]


@dataclass(frozen=True)
class CorrectionsCommand:
    action: CorrectionsActionName
    session_id: str
    action_id: str
    action_seq: int
    expected_session_revision: str
    expected_candidate_revision: Optional[str] = None
    candidate_id: Optional[str] = None
    protocol_version: str = PROTOCOL_VERSION
    frontend_build_id: str = "legacy"
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CorrectionsAck:
    action_id: str
    action_seq: int
    status: CorrectionsAckStatus
    session_id: str
    session_revision: str
    candidate_revision: Optional[str] = None
    message: Optional[str] = None
    # Apply/export must remain server-authoritative; never optimistic.
    apply_export_committed: bool = False
    # Opaque controller return (e.g. export path payload); never used for optimism.
    result: Any = None


def new_corrections_action_id() -> str:
    return uuid.uuid4().hex


class CorrectionsActionService:
    """Idempotent corrections command executor (domain façade).

    Candidate IDs alone are insufficient — callers must supply session and
    candidate revisions. ``apply_export`` is duplicate-safe and never implied
    by accept/reject.
    """

    def __init__(self, controller) -> None:
        self._controller = controller
        self._acks: dict[str, CorrectionsAck] = {}

    def execute(self, command: CorrectionsCommand) -> CorrectionsAck:
        prior = self._acks.get(command.action_id)
        if prior is not None:
            return prior
        if command.protocol_version != PROTOCOL_VERSION:
            ack = CorrectionsAck(
                action_id=command.action_id,
                action_seq=command.action_seq,
                status="rejected_protocol",
                session_id=command.session_id,
                session_revision=command.expected_session_revision,
                message="Protocol mismatch",
            )
            self._acks[command.action_id] = ack
            return ack

        # Revision checks are enforced against controller-reported facts when available.
        current_session_rev = getattr(
            self._controller, "session_revision", lambda _s: command.expected_session_revision
        )(command.session_id)
        if current_session_rev != command.expected_session_revision:
            ack = CorrectionsAck(
                action_id=command.action_id,
                action_seq=command.action_seq,
                status="rejected_stale",
                session_id=command.session_id,
                session_revision=str(current_session_rev),
                message="Session changed underfoot",
            )
            self._acks[command.action_id] = ack
            return ack

        if command.action == "apply_export":
            # Explicit, server-authoritative, duplicate-safe.
            apply = getattr(self._controller, "apply_and_export", None)
            if apply is None:
                ack = CorrectionsAck(
                    action_id=command.action_id,
                    action_seq=command.action_seq,
                    status="error",
                    session_id=command.session_id,
                    session_revision=command.expected_session_revision,
                    message="apply_and_export unavailable",
                )
            else:
                try:
                    export_result = apply(command.session_id, **dict(command.payload))
                except Exception as exc:  # noqa: BLE001 — surface as ack error
                    ack = CorrectionsAck(
                        action_id=command.action_id,
                        action_seq=command.action_seq,
                        status="error",
                        session_id=command.session_id,
                        session_revision=command.expected_session_revision,
                        message=str(exc) or "apply_and_export failed",
                    )
                    self._acks[command.action_id] = ack
                    return ack
                ack = CorrectionsAck(
                    action_id=command.action_id,
                    action_seq=command.action_seq,
                    status="ok",
                    session_id=command.session_id,
                    session_revision=command.expected_session_revision,
                    apply_export_committed=True,
                    result=export_result,
                )
            self._acks[command.action_id] = ack
            return ack

        if command.expected_candidate_revision is not None and command.candidate_id:
            cand_rev = getattr(
                self._controller,
                "candidate_revision",
                lambda _s, _c: command.expected_candidate_revision,
            )(command.session_id, command.candidate_id)
            if cand_rev != command.expected_candidate_revision:
                ack = CorrectionsAck(
                    action_id=command.action_id,
                    action_seq=command.action_seq,
                    status="rejected_stale",
                    session_id=command.session_id,
                    session_revision=command.expected_session_revision,
                    candidate_revision=str(cand_rev),
                    message="Candidate changed underfoot",
                )
                self._acks[command.action_id] = ack
                return ack

        record = getattr(self._controller, "record_decision", None)
        if command.action in {"accept", "reject", "skip"} and record is not None:
            record(
                command.session_id,
                command.candidate_id,
                command.action,
                **dict(command.payload),
            )

        ack = CorrectionsAck(
            action_id=command.action_id,
            action_seq=command.action_seq,
            status="ok",
            session_id=command.session_id,
            session_revision=command.expected_session_revision,
            candidate_revision=command.expected_candidate_revision,
        )
        self._acks[command.action_id] = ack
        return ack
