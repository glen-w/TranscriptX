"""Pure dict helpers for Corrections Studio UI (API/legacy field names)."""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence


def studio_session_id(session_data: Mapping[str, Any]) -> Optional[str]:
    return session_data.get("session_id") or session_data.get("id")


def studio_candidate_id(candidate: Mapping[str, Any]) -> Optional[str]:
    return candidate.get("candidate_id") or candidate.get("candidate_hash")


def studio_candidate_review_status(candidate: Mapping[str, Any]) -> str:
    return candidate.get("review_status") or candidate.get("status", "pending")


def studio_candidate_right_text(candidate: Mapping[str, Any]) -> str:
    return candidate.get("right_text") or candidate.get("suggested_text", "")


def studio_candidate_effective_right_text(
    candidate: Mapping[str, Any],
    review_records: Sequence[Mapping[str, Any]],
    generation_id: int,
) -> str:
    """Same effective target as compile (latest review wins for that generation)."""
    from transcriptx.services.corrections_studio.review_target import (
        effective_right_for_candidate,
    )
    from transcriptx.services.corrections_studio.schema import (
        StudioCandidate,
        StudioReviewRecord,
    )

    c = StudioCandidate.model_validate(candidate)
    revs = [
        StudioReviewRecord.model_validate(r)
        for r in review_records
        if isinstance(r, Mapping)
    ]
    return effective_right_for_candidate(
        candidate=c, reviews=revs, generation_id=generation_id
    )
