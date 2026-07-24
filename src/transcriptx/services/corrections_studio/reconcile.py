"""Rebuild studio snapshot from authoritative events.jsonl stream."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

from pydantic import TypeAdapter

from transcriptx.services.corrections_studio.review_target import (
    normalize_review_target_text,
)
from transcriptx.services.corrections_studio.schema import (
    ApplyScope,
    GenerationManifest,
    ReviewAction,
    ReviewStatus,
    RuleLifecycleState,
    StudioCandidate,
    StudioEventEnvelope,
    StudioReviewRecord,
    StudioRule,
    StudioSessionDocument,
)


def _status_for_action(action: ReviewAction) -> ReviewStatus:
    if action == ReviewAction.accept or action == ReviewAction.learn:
        return ReviewStatus.accepted
    if action == ReviewAction.reject:
        return ReviewStatus.rejected
    if action == ReviewAction.skip:
        return ReviewStatus.skipped
    return ReviewStatus.pending


@dataclass
class _ReplayState:
    doc: Dict[str, Any] = field(default_factory=dict)
    candidates_by_id: Dict[str, StudioCandidate] = field(default_factory=dict)
    reviews: List[StudioReviewRecord] = field(default_factory=list)


def _replay_session_started(state: _ReplayState, env: StudioEventEnvelope) -> None:
    payload = env.payload or {}
    state.doc = {
        "studio_schema_version": 1,
        "session_id": env.session_id,
        "transcript_path": payload.get("transcript_path", ""),
        "recorded_transcript_identity_hash": payload.get(
            "recorded_transcript_identity_hash", ""
        ),
        "current_generation_id": None,
        "candidates": [],
        "review_records": [],
        "rules": {},
        "created_at": env.timestamp,
        "updated_at": env.timestamp,
        "status": "active",
        "staleness_status": "ok",
    }
    state.candidates_by_id = {}
    state.reviews = []


def _replay_candidates_generated(state: _ReplayState, env: StudioEventEnvelope) -> None:
    doc = state.doc
    payload = env.payload or {}
    gen_id = int(payload.get("generation_id", 1))
    doc["current_generation_id"] = gen_id
    if payload.get("generation_manifest") and payload.get("generation_manifest_hash"):
        man = GenerationManifest.model_validate(payload["generation_manifest"])
        gen_blob: dict = {
            "generation_id": gen_id,
            "generation_manifest": man.model_dump(mode="json"),
            "generation_manifest_hash": payload["generation_manifest_hash"],
            "candidate_ids": list(payload.get("candidate_ids") or []),
            "completed_at": env.timestamp,
        }
        diag = payload.get("diagnostics")
        if isinstance(diag, dict):
            gen_blob["generation_diagnostics"] = diag
        doc["current_generation"] = gen_blob
    raw_cands = payload.get("candidates") or []
    state.candidates_by_id = {}
    for c in raw_cands:
        if isinstance(c, dict):
            sc = StudioCandidate.model_validate(c)
            state.candidates_by_id[sc.candidate_id] = sc
    doc["candidates"] = list(state.candidates_by_id.values())
    state.reviews = [r for r in state.reviews if r.generation_id != gen_id]


def _replay_review_recorded(state: _ReplayState, env: StudioEventEnvelope) -> None:
    doc = state.doc
    payload = env.payload or {}
    gen_id = int(payload.get("generation_id", doc.get("current_generation_id") or 1))
    cand_id = str(payload.get("candidate_id", ""))
    action = ReviewAction(payload.get("review_action", "skip"))
    scope = ApplyScope(payload.get("apply_scope", "all"))
    keys = [str(x) for x in (payload.get("selected_occurrence_keys") or [])]
    lr = payload.get("learn_rule_id")
    rt = normalize_review_target_text(payload.get("review_target_text"))
    migrated = payload.get("migrated_from_generation_id")
    rec = StudioReviewRecord(
        session_id=env.session_id,
        generation_id=gen_id,
        candidate_id=cand_id,
        review_action=action,
        apply_scope=scope,
        selected_occurrence_keys=keys,
        learn_rule_id=str(lr) if lr else None,
        review_target_text=rt,
        recorded_at=env.timestamp,
        event_sequence=env.event_sequence,
        migrated_from_generation_id=(int(migrated) if migrated is not None else None),
    )
    reviews = [
        r
        for r in state.reviews
        if not (r.candidate_id == cand_id and r.generation_id == gen_id)
    ]
    reviews.append(rec)
    state.reviews = reviews
    if cand_id in state.candidates_by_id:
        c = state.candidates_by_id[cand_id]
        state.candidates_by_id[cand_id] = c.model_copy(
            update={"review_status": _status_for_action(action)}
        )
    doc["review_records"] = state.reviews
    doc["candidates"] = list(state.candidates_by_id.values())


def _replay_rule_state_changed(state: _ReplayState, env: StudioEventEnvelope) -> None:
    doc = state.doc
    payload = env.payload or {}
    rule_id = str(payload.get("rule_id") or "")
    if not rule_id:
        return
    change = str(payload.get("change") or "upsert")
    rules = dict(doc.get("rules") or {})
    if change == "disable":
        existing = rules.get(rule_id)
        if isinstance(existing, StudioRule):
            rules[rule_id] = existing.model_copy(
                update={"lifecycle": RuleLifecycleState.disabled}
            )
        elif isinstance(existing, dict):
            existing = dict(existing)
            existing["lifecycle"] = RuleLifecycleState.disabled.value
            rules[rule_id] = existing
        doc["rules"] = rules
        return
    if change == "enable":
        existing = rules.get(rule_id)
        if isinstance(existing, StudioRule):
            rules[rule_id] = existing.model_copy(
                update={"lifecycle": RuleLifecycleState.session_active}
            )
        elif isinstance(existing, dict):
            existing = dict(existing)
            existing["lifecycle"] = RuleLifecycleState.session_active.value
            rules[rule_id] = existing
        doc["rules"] = rules
        return
    raw_rule = payload.get("rule")
    if isinstance(raw_rule, dict):
        try:
            rules[rule_id] = StudioRule.model_validate(raw_rule)
        except Exception:
            return
        doc["rules"] = rules


def _replay_noop(_state: _ReplayState, _env: StudioEventEnvelope) -> None:
    return None


_EVENT_HANDLERS: Dict[str, Callable[[_ReplayState, StudioEventEnvelope], None]] = {
    "session_started": _replay_session_started,
    "candidates_generated": _replay_candidates_generated,
    "review_recorded": _replay_review_recorded,
    "preview_computed": _replay_noop,
    "export_completed": _replay_noop,
    "rule_state_changed": _replay_rule_state_changed,
    "session_forked": _replay_noop,
    "staleness_detected": _replay_noop,
    "incompatible_transcript_detected": _replay_noop,
}


def reconcile_snapshot_from_events(
    *,
    events: List[StudioEventEnvelope],
) -> StudioSessionDocument:
    """
    Deterministic replay of typed events into a StudioSessionDocument.

    First event should be session_started; candidates_generated supplies candidate rows.
    """
    state = _ReplayState()
    sorted_events = sorted(events, key=lambda e: e.event_sequence)
    last_env: StudioEventEnvelope | None = None
    for env in sorted_events:
        last_env = env
        handler = _EVENT_HANDLERS.get(env.event_type, _replay_noop)
        handler(state, env)

    doc = state.doc
    if not doc:
        raise ValueError("No session_started event in stream")

    doc["review_records"] = state.reviews
    doc["candidates"] = list(state.candidates_by_id.values())
    if last_env is not None:
        doc["updated_at"] = last_env.timestamp
    from transcriptx.services.corrections_studio.normalize import (
        migrate_session_document_to_v2,
    )

    rebuilt = StudioSessionDocument.model_validate(doc)
    return migrate_session_document_to_v2(rebuilt)


def parse_events_jsonl(lines: List[str]) -> List[StudioEventEnvelope]:
    adapter: TypeAdapter[StudioEventEnvelope] = TypeAdapter(StudioEventEnvelope)
    out: List[StudioEventEnvelope] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        data = json.loads(line)
        out.append(adapter.validate_python(data))
    return out
