"""Optimistic commit of a generation batch for Corrections Studio."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from transcriptx.services.corrections_studio.schema import (
    CandidateGenerationDiagnostics,
    CandidatesGeneratedPayload,
    GenerationOrigin,
    ReviewStatus,
    StudioCandidate,
    StudioEventEnvelope,
    StudioGenerationRecord,
    StudioSessionDocument,
)
from transcriptx.services.corrections_studio.session_service import (
    CorrectionsStudioSessionService,
)


def commit_generation_batch(
    *,
    session_service: CorrectionsStudioSessionService,
    session_id: str,
    transcript_path: str,
    prior_doc: StudioSessionDocument,
    new_gen: int,
    manifest: Any,
    mh: str,
    diagnostics: CandidateGenerationDiagnostics,
    studio_candidates: List[StudioCandidate],
    migration_payloads: List[Any],
    expected_last_event_sequence: int,
    expected_generation_id: Optional[int],
    expected_transcript_identity_hash: str,
    expected_rules_fp: str,
    generation_origin: GenerationOrigin = GenerationOrigin.detector,
    historical_candidates: Optional[List[StudioCandidate]] = None,
) -> List[StudioCandidate]:
    from transcriptx.services.corrections_studio.schema import (
        ReviewAction,
        StudioReviewRecord,
    )
    from transcriptx.services.corrections_studio.session_service import (
        PersistPreconditions,
    )

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    review_records = [r for r in prior_doc.review_records if r.generation_id != new_gen]
    status_by_cand: Dict[str, ReviewStatus] = {}
    for mp in migration_payloads:
        action = mp.review_action
        if action in (ReviewAction.accept, ReviewAction.learn):
            st = ReviewStatus.accepted
        elif action == ReviewAction.reject:
            st = ReviewStatus.rejected
        else:
            # skip / unknown → pending (legacy migration contract)
            st = ReviewStatus.pending
        status_by_cand[mp.candidate_id] = st
        review_records.append(
            StudioReviewRecord(
                session_id=session_id,
                generation_id=new_gen,
                candidate_id=mp.candidate_id,
                review_action=action,
                apply_scope=mp.apply_scope,
                selected_occurrence_keys=list(mp.selected_occurrence_keys),
                learn_intent=mp.learn_intent,
                learn_rule_id=mp.learn_rule_id,
                review_target_text=mp.review_target_text,
                recorded_at=now,
                event_sequence=0,
                migrated_from_generation_id=mp.migrated_from_generation_id,
            )
        )

    cands = [
        c.model_copy(
            update={
                "review_status": status_by_cand.get(
                    c.candidate_id, ReviewStatus.pending
                )
            }
        )
        for c in studio_candidates
    ]
    # Keep prior-generation candidates for audit; current list is cands for new_gen.
    hist = [c for c in (historical_candidates or []) if c.generation_id != new_gen]
    all_cands = hist + cands
    doc = prior_doc.model_copy(
        update={
            "current_generation_id": new_gen,
            "current_generation": StudioGenerationRecord(
                generation_id=new_gen,
                generation_manifest=manifest,
                generation_manifest_hash=mh,
                candidate_ids=[c.candidate_id for c in cands],
                completed_at=now,
                generation_diagnostics=diagnostics,
                generation_origin=generation_origin,
            ),
            "candidates": all_cands,
            "review_records": review_records,
            "updated_at": now,
            "studio_schema_version": 1,
        }
    )
    if not doc.created_at:
        doc = doc.model_copy(update={"created_at": now})

    cand_payload = CandidatesGeneratedPayload(
        generation_id=new_gen,
        generation_manifest=manifest,
        generation_manifest_hash=mh,
        candidate_ids=[c.candidate_id for c in cands],
        candidates=[c.model_dump(mode="json") for c in cands],
        diagnostics=diagnostics,
    )
    events: List[StudioEventEnvelope] = [
        StudioEventEnvelope(
            session_id=session_id,
            event_type="candidates_generated",
            event_sequence=0,
            generation_id=new_gen,
            payload=cand_payload.model_dump(mode="json"),
            payload_schema_version=2,
            timestamp=now,
        )
    ]
    for mp in migration_payloads:
        events.append(
            StudioEventEnvelope(
                session_id=session_id,
                event_type="review_recorded",
                event_sequence=0,
                generation_id=new_gen,
                payload=mp.model_dump(mode="json"),
                payload_schema_version=2,
                timestamp=now,
            )
        )
    pre = PersistPreconditions(
        expected_last_event_sequence=expected_last_event_sequence,
        expected_current_generation_id=expected_generation_id,
        expected_transcript_identity_hash=expected_transcript_identity_hash,
        expected_studio_session_rules_fingerprint=expected_rules_fp,
        check_generation_id=True,
    )
    session_service.persist_event_batch(transcript_path, doc, events, preconditions=pre)
    return cands
