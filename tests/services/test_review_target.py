"""review_target helpers for Corrections Studio."""

from __future__ import annotations

from datetime import datetime, timezone

from transcriptx.services.corrections_studio.review_target import (
    effective_right_for_candidate,
    is_custom_review_target,
    normalize_review_target_text,
    persisted_review_target_text,
    resolve_effective_right,
)
from transcriptx.services.corrections_studio.schema import (
    ReviewAction,
    ReviewStatus,
    StudioCandidate,
    StudioReviewRecord,
)


def test_normalize_review_target_text() -> None:
    assert normalize_review_target_text(None) is None
    assert normalize_review_target_text("") is None
    assert normalize_review_target_text("  ") is None
    assert normalize_review_target_text(" GO ") == "GO"


def test_resolve_effective_right() -> None:
    assert (
        resolve_effective_right(
            candidate_right_text="Geo", review_target_normalized=None
        )
        == "Geo"
    )
    assert (
        resolve_effective_right(
            candidate_right_text="Geo", review_target_normalized="GO"
        )
        == "GO"
    )


def test_persisted_review_target_text_collapses_default() -> None:
    assert (
        persisted_review_target_text(raw_override="  Geo  ", candidate_right_text="Geo")
        is None
    )
    assert (
        persisted_review_target_text(raw_override="GO", candidate_right_text="Geo")
        == "GO"
    )


def test_is_custom_review_target() -> None:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    c = StudioCandidate(
        candidate_id="c1",
        generation_id=1,
        kind="consistency",
        wrong_text="GEO",
        right_text="Geo",
        confidence=1.0,
        occurrences=[],
        review_status=ReviewStatus.accepted,
    )
    r_plain = StudioReviewRecord(
        session_id="s",
        generation_id=1,
        candidate_id="c1",
        review_action=ReviewAction.accept,
        recorded_at=now,
        event_sequence=1,
        review_target_text=None,
    )
    assert not is_custom_review_target(c, r_plain)
    r_custom = r_plain.model_copy(update={"review_target_text": "GO"})
    assert is_custom_review_target(c, r_custom)


def test_effective_right_for_candidate_latest_wins() -> None:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    c = StudioCandidate(
        candidate_id="c1",
        generation_id=1,
        kind="acronym",
        wrong_text="a",
        right_text="b",
        confidence=0.9,
        occurrences=[],
        review_status=ReviewStatus.accepted,
    )
    r1 = StudioReviewRecord(
        session_id="s",
        generation_id=1,
        candidate_id="c1",
        review_action=ReviewAction.accept,
        review_target_text="first",
        recorded_at=now,
        event_sequence=1,
    )
    r2 = StudioReviewRecord(
        session_id="s",
        generation_id=1,
        candidate_id="c1",
        review_action=ReviewAction.accept,
        review_target_text="second",
        recorded_at=now,
        event_sequence=2,
    )
    eff = effective_right_for_candidate(candidate=c, reviews=[r1, r2], generation_id=1)
    assert eff == "second"


def test_effective_right_no_reviews() -> None:
    c = StudioCandidate(
        candidate_id="c1",
        generation_id=1,
        kind="acronym",
        wrong_text="a",
        right_text="b",
        confidence=0.9,
        occurrences=[],
        review_status=ReviewStatus.pending,
    )
    assert (
        effective_right_for_candidate(candidate=c, reviews=[], generation_id=1) == "b"
    )
