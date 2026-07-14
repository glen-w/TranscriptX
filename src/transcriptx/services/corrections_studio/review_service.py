"""CorrectionsStudioReviewService: builds review_recorded event payloads; SessionService persists."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from transcriptx.services.corrections_studio.review_target import (
    persisted_review_target_text,
)
from transcriptx.services.corrections_studio.schema import (
    ApplyScope,
    LearnIntent,
    ReviewAction,
    ReviewRecordedPayload,
    ReviewStatus,
    RuleLifecycleState,
    RuleStateChangedPayload,
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
        review_target_raw: Optional[str] = None,
    ) -> None:
        doc = self._session.load_document(session_id)
        gen = doc.current_generation_id
        if gen is None:
            raise ValueError("No active generation; generate candidates first")

        sc = next(
            (
                c
                for c in doc.candidates
                if c.candidate_id == candidate_id and c.generation_id == gen
            ),
            None,
        )
        learn_rule_id: Optional[str] = None
        sr: Optional[StudioRule] = None
        if learn_rule_params:
            sr = StudioRule(
                rule_id=str(learn_rule_params["rule_hash"]),
                rule_type=str(learn_rule_params["rule_type"]),
                wrong_variants=list(learn_rule_params["wrong_variants_json"]),
                replacement_text=str(learn_rule_params["replacement_text"]),
                scope=str(learn_rule_params.get("scope", "global")),
                confidence=float(learn_rule_params.get("confidence", 0.0)),
                auto_apply=bool(learn_rule_params.get("auto_apply", False)),
                lifecycle=RuleLifecycleState.session_active,
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

        review_target_text: Optional[str] = None
        if action in (ReviewAction.accept, ReviewAction.learn):
            review_target_text = persisted_review_target_text(
                raw_override=review_target_raw,
                candidate_right_text=sc.right_text if sc else "",
            )

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        # Placeholder; locked batch writer allocates the real event_sequence.
        placeholder_seq = 0

        rec = StudioReviewRecord(
            session_id=session_id,
            generation_id=gen,
            candidate_id=candidate_id,
            review_action=action,
            apply_scope=scope,
            selected_occurrence_keys=keys,
            learn_intent=LearnIntent.create_rule if learn_rule_params else None,
            learn_rule_id=learn_rule_id,
            review_target_text=review_target_text,
            recorded_at=now,
            event_sequence=placeholder_seq,
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

        events: List[StudioEventEnvelope] = []
        if sr is not None:
            rule_payload = RuleStateChangedPayload(
                rule_id=sr.rule_id,
                change="upsert",
                rule=sr.model_dump(mode="json"),
            )
            events.append(
                StudioEventEnvelope(
                    session_id=session_id,
                    event_type="rule_state_changed",
                    event_sequence=placeholder_seq,
                    generation_id=gen,
                    payload=rule_payload.model_dump(mode="json"),
                    timestamp=now,
                )
            )

        payload = ReviewRecordedPayload(
            generation_id=gen,
            candidate_id=candidate_id,
            review_action=action,
            apply_scope=scope,
            selected_occurrence_keys=keys,
            learn_intent=rec.learn_intent,
            learn_rule_id=learn_rule_id,
            review_target_text=review_target_text,
        )
        events.append(
            StudioEventEnvelope(
                session_id=session_id,
                event_type="review_recorded",
                event_sequence=placeholder_seq,
                generation_id=gen,
                payload=payload.model_dump(mode="json"),
                timestamp=now,
            )
        )
        self._session.persist_event_batch(doc.transcript_path, doc, events)
