"""CorrectionsStudioReviewService: builds review_recorded event payloads; SessionService persists."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from transcriptx.services.corrections_studio.schema import (
    ApplyScope,
    LearnIntent,
    ReviewAction,
    ReviewRecordedPayload,
    ReviewStatus,
    StudioEventEnvelope,
    StudioReviewRecord,
    StudioRule,
)
from transcriptx.services.corrections_studio.session_service import (
    CorrectionsStudioSessionService,
)


def _status_for_action(action: ReviewAction) -> ReviewStatus:
    if action in (ReviewAction.accept, ReviewAction.learn):
        return ReviewStatus.accepted
    if action == ReviewAction.reject:
        return ReviewStatus.rejected
    if action == ReviewAction.skip:
        return ReviewStatus.skipped
    return ReviewStatus.pending


class CorrectionsStudioReviewService:
    def __init__(self, session_service: CorrectionsStudioSessionService) -> None:
        self._session = session_service

    def record_decision(
        self,
        session_id: str,
        candidate_id: str,
        decision: str,
        selected_occurrence_keys: Optional[List[str]] = None,
        learn_rule_params: Optional[Dict[str, Any]] = None,
    ) -> None:
        doc = self._session.load_document(session_id)
        gen = doc.current_generation_id
        if gen is None:
            raise ValueError("No active generation; generate candidates first")

        learn_rule_id: Optional[str] = None
        if learn_rule_params:
            sr = StudioRule(
                rule_id=str(learn_rule_params["rule_hash"]),
                rule_type=str(learn_rule_params["rule_type"]),
                wrong_variants=list(learn_rule_params["wrong_variants_json"]),
                replacement_text=str(learn_rule_params["replacement_text"]),
                scope=str(learn_rule_params.get("scope", "global")),
                confidence=float(learn_rule_params.get("confidence", 0.0)),
                auto_apply=bool(learn_rule_params.get("auto_apply", False)),
            )
            new_rules = dict(doc.rules)
            new_rules[sr.rule_id] = sr
            doc = doc.model_copy(update={"rules": new_rules})
            learn_rule_id = sr.rule_id
            action = ReviewAction.learn
        else:
            action = ReviewAction(decision)

        scope = ApplyScope.selected if selected_occurrence_keys else ApplyScope.all
        keys = [str(x) for x in (selected_occurrence_keys or [])]

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        seq = self._session.next_event_sequence(session_id)

        rec = StudioReviewRecord(
            session_id=session_id,
            generation_id=gen,
            candidate_id=candidate_id,
            review_action=action,
            apply_scope=scope,
            selected_occurrence_keys=keys,
            learn_intent=LearnIntent.create_rule if learn_rule_params else None,
            learn_rule_id=learn_rule_id,
            recorded_at=now,
            event_sequence=seq,
        )

        kept = [
            r
            for r in doc.review_records
            if not (r.candidate_id == candidate_id and r.generation_id == gen)
        ]
        kept.append(rec)

        st = _status_for_action(action)
        new_cands = [
            (
                c.model_copy(update={"review_status": st})
                if c.candidate_id == candidate_id and c.generation_id == gen
                else c
            )
            for c in doc.candidates
        ]

        doc = doc.model_copy(
            update={"review_records": kept, "candidates": new_cands, "updated_at": now}
        )

        payload = ReviewRecordedPayload(
            generation_id=gen,
            candidate_id=candidate_id,
            review_action=action,
            apply_scope=scope,
            selected_occurrence_keys=keys,
            learn_intent=rec.learn_intent,
            learn_rule_id=learn_rule_id,
        )
        event = StudioEventEnvelope(
            session_id=session_id,
            event_type="review_recorded",
            event_sequence=seq,
            generation_id=gen,
            payload=payload.model_dump(mode="json"),
        )
        self._session.persist(doc.transcript_path, doc, event)
