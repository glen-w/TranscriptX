"""Assemble CCv2 Corrections Studio review data + dispatch commands."""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from transcriptx.app.corrections import (
    PROTOCOL_VERSION,
    CorrectionsActionService,
    CorrectionsCommand,
)

try:
    from transcriptx_workspaces import FRONTEND_BUILD_ID
except Exception:  # pragma: no cover
    FRONTEND_BUILD_ID = "tx-workspaces-0.3.0"


def stable_corrections_workspace_key(session_id: str) -> str:
    return f"corrections_ws:{session_id}"


def command_from_workspace_result(result: Any) -> Optional[dict[str, Any]]:
    if result is None:
        return None
    command = getattr(result, "command", None)
    if command is None and isinstance(result, Mapping):
        command = result.get("command")
    if not command:
        return None
    if isinstance(command, Mapping) and not isinstance(command, dict):
        command = dict(command)
    if not isinstance(command, dict):
        return None
    if not str(command.get("action") or "").strip():
        return None
    return command


def _candidate_row(candidate: Any) -> dict[str, Any]:
    cid = getattr(candidate, "candidate_id", None) or ""
    status = getattr(candidate, "review_status", None)
    status_s = (
        status.value if hasattr(status, "value") else (str(status) if status else "")
    )
    sources = []
    viewer = False
    for s in getattr(candidate, "sources", None) or []:
        val = s.value if hasattr(s, "value") else str(s)
        sources.append(val)
        if val == "viewer_manual":
            viewer = True
    digest = (
        getattr(candidate, "suggestion_digest", None)
        or getattr(candidate, "digest", None)
        or ""
    )
    kind = getattr(candidate, "kind", "") or ""
    return {
        "id": cid,
        "kind": kind,
        "status": status_s,
        "wrong_text": str(getattr(candidate, "wrong_text", "") or ""),
        "right_text": str(getattr(candidate, "right_text", "") or ""),
        "confidence": float(getattr(candidate, "confidence", 0.0) or 0.0),
        "revision": f"cand:{cid}:{status_s}:{digest}",
        "sources": sources,
        "viewer": viewer or kind == "manual",
    }


def build_corrections_workspace_data(
    *,
    session_id: str,
    session_revision: str,
    candidates: Sequence[Any],
    active_candidate: Any | None,
    last_ack: Optional[Mapping[str, Any]] = None,
    ui_status: str = "",
) -> dict[str, Any]:
    rows = [_candidate_row(c) for c in candidates if getattr(c, "candidate_id", None)]
    active_id = getattr(active_candidate, "candidate_id", None) if active_candidate else None
    active_payload = None
    if active_candidate is not None and active_id:
        row = _candidate_row(active_candidate)
        evidence = getattr(active_candidate, "evidence", None)
        rationale = getattr(evidence, "rationale", None) if evidence else None
        active_payload = {
            "id": row["id"],
            "kind": row["kind"],
            "status": row["status"],
            "wrong_text": row["wrong_text"],
            "right_text": row["right_text"],
            "revision": row["revision"],
            "rationale": rationale,
        }
    return {
        "protocol_version": PROTOCOL_VERSION,
        "frontend_build_id": FRONTEND_BUILD_ID,
        "session_id": session_id,
        "session_revision": session_revision,
        "active_candidate_id": active_id,
        "candidates": rows,
        "active": active_payload,
        "ack": dict(last_ack) if last_ack else None,
        "ui": {"status": ui_status, "disabled": False},
    }


def dispatch_corrections_command(
    command: Mapping[str, Any] | None,
    *,
    service: CorrectionsActionService,
    session_id: str,
    session_revision: str,
) -> Optional[dict[str, Any]]:
    if not command:
        return None
    action = str(command.get("action") or "")
    if action == "protocol_mismatch":
        return {
            "action_id": command.get("action_id"),
            "action_seq": int(command.get("action_seq") or 0),
            "status": "rejected_protocol",
            "message": "Frontend/protocol mismatch — reload Corrections Studio.",
        }
    payload = dict(command.get("payload") or {})
    if action == "select_candidate":
        return {
            "action_id": command.get("action_id"),
            "action_seq": int(command.get("action_seq") or 0),
            "status": "ok",
            "message": None,
            "selected_candidate_id": payload.get("candidate_id")
            or command.get("candidate_id"),
        }
    cmd = CorrectionsCommand(
        action=action,  # type: ignore[arg-type]
        session_id=str(command.get("session_id") or session_id),
        action_id=str(command.get("action_id") or ""),
        action_seq=int(command.get("action_seq") or 0),
        expected_session_revision=str(
            command.get("expected_session_revision") or session_revision
        ),
        expected_candidate_revision=command.get("expected_candidate_revision"),
        candidate_id=command.get("candidate_id"),
        protocol_version=str(command.get("protocol_version") or PROTOCOL_VERSION),
        frontend_build_id=str(command.get("frontend_build_id") or FRONTEND_BUILD_ID),
        payload=payload,
    )
    ack = service.execute(cmd)
    return {
        "action_id": ack.action_id,
        "action_seq": ack.action_seq,
        "status": ack.status,
        "message": ack.message,
        "session_revision": ack.session_revision,
        "candidate_revision": ack.candidate_revision,
        "apply_export_committed": ack.apply_export_committed,
    }
