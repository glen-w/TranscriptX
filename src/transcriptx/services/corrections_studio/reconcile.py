"""Rebuild studio snapshot from authoritative events.jsonl stream."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from pydantic import TypeAdapter

from transcriptx.services.corrections_studio.schema import (
    ApplyScope,
    ReviewAction,
    ReviewStatus,
    StudioCandidate,
    StudioEventEnvelope,
    StudioReviewRecord,
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


def reconcile_snapshot_from_events(
    *,
    events: List[StudioEventEnvelope],
) -> StudioSessionDocument:
    """
    Deterministic replay of typed events into a StudioSessionDocument.

    First event should be session_started; candidates_generated supplies candidate rows.
    """
    doc: Dict[str, Any] = {}
    candidates_by_id: Dict[str, StudioCandidate] = {}
    reviews: List[StudioReviewRecord] = []
    for env in sorted(events, key=lambda e: e.event_sequence):
        payload = env.payload or {}
        et = env.event_type

        if et == "session_started":
            doc = {
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
            candidates_by_id = {}
            reviews = []

        elif et == "candidates_generated":
            gen_id = int(payload.get("generation_id", 1))
            doc["current_generation_id"] = gen_id
            if payload.get("generation_manifest") and payload.get(
                "generation_manifest_hash"
            ):
                from transcriptx.services.corrections_studio.schema import (
                    GenerationManifest,
                )

                man = GenerationManifest.model_validate(payload["generation_manifest"])
                doc["current_generation"] = {
                    "generation_id": gen_id,
                    "generation_manifest": man.model_dump(mode="json"),
                    "generation_manifest_hash": payload["generation_manifest_hash"],
                    "candidate_ids": list(payload.get("candidate_ids") or []),
                    "completed_at": env.timestamp,
                }
            raw_cands = payload.get("candidates") or []
            candidates_by_id = {}
            for c in raw_cands:
                if isinstance(c, dict):
                    sc = StudioCandidate.model_validate(c)
                    candidates_by_id[sc.candidate_id] = sc
            doc["candidates"] = list(candidates_by_id.values())
            # drop reviews from prior generation
            reviews = [r for r in reviews if r.generation_id != gen_id]

        elif et == "review_recorded":
            gen_id = int(
                payload.get("generation_id", doc.get("current_generation_id") or 1)
            )
            cand_id = str(payload.get("candidate_id", ""))
            action = ReviewAction(payload.get("review_action", "skip"))
            scope = ApplyScope(payload.get("apply_scope", "all"))
            keys = [str(x) for x in (payload.get("selected_occurrence_keys") or [])]
            lr = payload.get("learn_rule_id")
            rec = StudioReviewRecord(
                session_id=env.session_id,
                generation_id=gen_id,
                candidate_id=cand_id,
                review_action=action,
                apply_scope=scope,
                selected_occurrence_keys=keys,
                learn_rule_id=str(lr) if lr else None,
                recorded_at=env.timestamp,
                event_sequence=env.event_sequence,
            )
            reviews = [
                r
                for r in reviews
                if not (r.candidate_id == cand_id and r.generation_id == gen_id)
            ]
            reviews.append(rec)
            if cand_id in candidates_by_id:
                c = candidates_by_id[cand_id]
                candidates_by_id[cand_id] = c.model_copy(
                    update={"review_status": _status_for_action(action)}
                )
            doc["review_records"] = reviews
            doc["candidates"] = list(candidates_by_id.values())

        elif et in (
            "preview_computed",
            "export_completed",
            "rule_state_changed",
            "session_forked",
            "staleness_detected",
            "incompatible_transcript_detected",
        ):
            continue

    if not doc:
        raise ValueError("No session_started event in stream")

    doc["review_records"] = reviews
    doc["candidates"] = list(candidates_by_id.values())
    doc["updated_at"] = events[-1].timestamp if events else doc.get("updated_at")
    return StudioSessionDocument.model_validate(doc)


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
