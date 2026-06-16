"""Normalization and effective target resolution for Corrections Studio review overrides."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from transcriptx.services.corrections_studio.schema import (
        StudioCandidate,
        StudioReviewRecord,
    )


def normalize_review_target_text(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    s = raw.strip()
    return s if s else None


def resolve_effective_right(
    *, candidate_right_text: str, review_target_normalized: Optional[str]
) -> str:
    if review_target_normalized is not None:
        return review_target_normalized
    return candidate_right_text


def persisted_review_target_text(
    *,
    raw_override: Optional[str],
    candidate_right_text: str,
) -> Optional[str]:
    """
    Normalized value to store on review_recorded (None = no durable override).

    Collapses overrides that match normalized generator right_text to avoid churn.
    """
    n = normalize_review_target_text(raw_override)
    if n is None:
        return None
    base = normalize_review_target_text(candidate_right_text)
    if base is not None and n == base:
        return None
    return n


def is_custom_review_target(
    candidate: "StudioCandidate", review: "StudioReviewRecord"
) -> bool:
    if review.review_target_text is None:
        return False
    eff = resolve_effective_right(
        candidate_right_text=candidate.right_text,
        review_target_normalized=review.review_target_text,
    )
    return normalize_review_target_text(eff) != normalize_review_target_text(
        candidate.right_text
    )


def effective_right_for_candidate(
    *,
    candidate: "StudioCandidate",
    reviews: list,
    generation_id: int,
) -> str:
    """Latest review for (candidate_id, generation_id) wins; then resolve_effective_right."""
    cand_id = candidate.candidate_id
    latest: Optional["StudioReviewRecord"] = None
    for r in sorted(
        (
            x
            for x in reviews
            if x.generation_id == generation_id and x.candidate_id == cand_id
        ),
        key=lambda x: x.event_sequence,
    ):
        latest = r
    if latest is None:
        return candidate.right_text
    return resolve_effective_right(
        candidate_right_text=candidate.right_text,
        review_target_normalized=latest.review_target_text,
    )
