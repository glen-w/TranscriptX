"""Explicit carry-forward of viewer_manual candidates across detector regenerations."""

from __future__ import annotations

from typing import List, Optional, Set, Tuple

from transcriptx.services.corrections_studio.schema import (
    ApplyScope,
    CandidateSource,
    ReviewAction,
    ReviewRecordedPayload,
    ReviewStatus,
    StudioCandidate,
    StudioReviewRecord,
)

_CARRY_ACTIONS = {
    ReviewAction.accept,
    ReviewAction.reject,
    ReviewAction.learn,
    ReviewAction.skip,
}


def is_viewer_manual_candidate(candidate: StudioCandidate) -> bool:
    if candidate.kind == "manual":
        return True
    for src in candidate.sources or []:
        val = src.value if hasattr(src, "value") else str(src)
        if val == CandidateSource.viewer_manual.value:
            return True
    return False


def _latest_reviews_for_generation(
    reviews: List[StudioReviewRecord], generation_id: Optional[int]
) -> dict[str, StudioReviewRecord]:
    if generation_id is None:
        return {}
    latest: dict[str, StudioReviewRecord] = {}
    for r in sorted(
        [x for x in reviews if x.generation_id == generation_id],
        key=lambda x: x.event_sequence,
    ):
        latest[r.candidate_id] = r
    return latest


def carry_forward_manual_candidates(
    *,
    prior_candidates: List[StudioCandidate],
    prior_reviews: List[StudioReviewRecord],
    prior_generation_id: Optional[int],
    new_generation_id: int,
) -> Tuple[List[StudioCandidate], List[ReviewRecordedPayload]]:
    """
    Preserve every viewer_manual / kind=manual candidate + latest review into new_gen.

    Independent of detector semantic migration — manuals absent from the regenerated
    detector set still survive with remapped generation_id.
    """
    if prior_generation_id is None:
        return [], []

    manuals = [
        c
        for c in prior_candidates
        if c.generation_id == prior_generation_id and is_viewer_manual_candidate(c)
    ]
    latest = _latest_reviews_for_generation(prior_reviews, prior_generation_id)
    carried_cands: List[StudioCandidate] = []
    carried_reviews: List[ReviewRecordedPayload] = []
    seen_ids: Set[str] = set()

    for prior in manuals:
        if prior.candidate_id in seen_ids:
            continue
        seen_ids.add(prior.candidate_id)
        status = prior.review_status
        rev = latest.get(prior.candidate_id)
        if rev is not None and rev.review_action in _CARRY_ACTIONS:
            if rev.review_action in (ReviewAction.accept, ReviewAction.learn):
                status = ReviewStatus.accepted
            elif rev.review_action == ReviewAction.reject:
                status = ReviewStatus.rejected
            elif rev.review_action == ReviewAction.skip:
                status = ReviewStatus.skipped
            carried_reviews.append(
                ReviewRecordedPayload(
                    generation_id=new_generation_id,
                    candidate_id=prior.candidate_id,
                    review_action=rev.review_action,
                    apply_scope=rev.apply_scope or ApplyScope.all,
                    selected_occurrence_keys=list(rev.selected_occurrence_keys or []),
                    learn_intent=rev.learn_intent,
                    learn_rule_id=rev.learn_rule_id,
                    review_target_text=rev.review_target_text,
                    migrated_from_generation_id=prior_generation_id,
                )
            )
        carried_cands.append(
            prior.model_copy(
                update={
                    "generation_id": new_generation_id,
                    "review_status": status,
                }
            )
        )
    return carried_cands, carried_reviews
