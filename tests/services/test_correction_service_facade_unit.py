"""CorrectionService façade methods (mocked sub-services)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from transcriptx.services.corrections_studio.schema import (
    ApplyScope,
    ReviewAction,
    ReviewStatus,
    StudioCandidate,
    StudioOccurrence,
    StudioReviewRecord,
    StudioSessionDocument,
)
from transcriptx.services.corrections_studio.service import CorrectionService


@pytest.mark.unit
def test_load_session_returns_none_when_store_misses() -> None:
    svc = CorrectionService()
    with patch.object(svc.repo, "find_by_session_id", return_value=None):
        assert svc.load_session("nope") is None


@pytest.mark.unit
def test_count_candidates_applies_filters() -> None:
    doc = StudioSessionDocument(
        session_id="s",
        transcript_path="/t.json",
        recorded_transcript_identity_hash="h",
        candidates=[
            StudioCandidate(
                candidate_id="c1",
                generation_id=1,
                kind="acronym",
                wrong_text="a",
                right_text="b",
                confidence=0.9,
                occurrences=[],
                review_status=ReviewStatus.pending,
            ),
            StudioCandidate(
                candidate_id="c2",
                generation_id=1,
                kind="phrase",
                wrong_text="x",
                right_text="y",
                confidence=0.2,
                occurrences=[],
                review_status=ReviewStatus.accepted,
            ),
        ],
    )
    svc = CorrectionService()
    with patch.object(svc._session_svc, "load_document", return_value=doc):
        n = svc.count_candidates(
            "s", status_filter="pending", kind_filter=["acronym"], confidence_min=0.5
        )
    assert n == 1


@pytest.mark.unit
def test_get_session_stats_counts_by_review_status() -> None:
    doc = StudioSessionDocument(
        session_id="s",
        transcript_path="/t.json",
        recorded_transcript_identity_hash="h",
        candidates=[
            StudioCandidate(
                candidate_id="a",
                generation_id=1,
                kind="k",
                wrong_text="w",
                right_text="r",
                confidence=1.0,
                occurrences=[],
                review_status=ReviewStatus.pending,
            ),
            StudioCandidate(
                candidate_id="b",
                generation_id=1,
                kind="k",
                wrong_text="w",
                right_text="r",
                confidence=1.0,
                occurrences=[],
                review_status=ReviewStatus.accepted,
            ),
            StudioCandidate(
                candidate_id="c",
                generation_id=1,
                kind="k",
                wrong_text="w",
                right_text="r",
                confidence=1.0,
                occurrences=[],
                review_status=ReviewStatus.rejected,
            ),
            StudioCandidate(
                candidate_id="d",
                generation_id=1,
                kind="k",
                wrong_text="w",
                right_text="r",
                confidence=1.0,
                occurrences=[],
                review_status=ReviewStatus.skipped,
            ),
        ],
    )
    svc = CorrectionService()
    with patch.object(svc._session_svc, "load_document", return_value=doc):
        st = svc.get_session_stats("s")
    assert st.pending == 1
    assert st.accepted == 1
    assert st.rejected == 1
    assert st.skipped == 1


@pytest.mark.unit
def test_get_candidate_local_diff_missing_candidate_empty_diffs() -> None:
    doc = StudioSessionDocument(
        session_id="s",
        transcript_path="/t.json",
        recorded_transcript_identity_hash="h",
        candidates=[],
    )
    svc = CorrectionService()
    with patch.object(svc._session_svc, "load_document", return_value=doc):
        out = svc.get_candidate_local_diff("s", "missing")
    assert out.diffs == []


@pytest.mark.unit
def test_get_candidate_local_diff_uses_review_accept_suggestion() -> None:
    doc = StudioSessionDocument(
        session_id="s",
        transcript_path="/t.json",
        recorded_transcript_identity_hash="h",
        current_generation_id=1,
        candidates=[
            StudioCandidate(
                candidate_id="c1",
                generation_id=1,
                kind="k",
                wrong_text="old",
                right_text="new",
                confidence=1.0,
                occurrences=[
                    StudioOccurrence(
                        segment_id="s0",
                        stable_occurrence_key="k0",
                        snippet="the old text",
                        segment_index=0,
                    )
                ],
                review_status=ReviewStatus.pending,
            )
        ],
        review_records=[
            StudioReviewRecord(
                session_id="s",
                generation_id=1,
                candidate_id="c1",
                review_action=ReviewAction.accept,
                apply_scope=ApplyScope.all,
                recorded_at="t",
                event_sequence=2,
                review_target_text="custom",
            )
        ],
    )
    svc = CorrectionService()
    with patch.object(svc._session_svc, "load_document", return_value=doc):
        out = svc.get_candidate_local_diff("s", "c1")
    assert len(out.diffs) == 1
    assert "custom" in out.diffs[0].after
