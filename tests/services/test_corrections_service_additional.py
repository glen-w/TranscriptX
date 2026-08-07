"""Tests for corrections service additional."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from transcriptx.services.corrections_studio.schema import (
    ReviewAction,
    ReviewStatus,
    StudioCandidate,
    StudioOccurrence,
    StudioReviewRecord,
)
from transcriptx.services.corrections_studio.service import CorrectionService


def _service_with_doc(doc):
    svc = CorrectionService()
    svc._session_svc = SimpleNamespace(load_document=lambda _sid: doc)
    return svc


def _doc(**kwargs):
    """Minimal session doc for CorrectionService unit tests."""
    base = {
        "candidates": [],
        "review_records": [],
        "current_generation_id": 1,
        "transcript_path": "/tmp/corrections_studio_fixture.json",
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


@pytest.mark.unit
def test_get_candidate_local_diff_returns_empty_when_candidate_missing():
    doc = _doc()
    svc = _service_with_doc(doc)
    diff = svc.get_candidate_local_diff("sid", "missing")
    assert diff.diffs == []


@pytest.mark.unit
def test_get_candidate_local_diff_uses_review_target_for_accept():
    cand = StudioCandidate(
        candidate_id="c1",
        generation_id=1,
        kind="consistency",
        wrong_text="foo",
        right_text="bar",
        confidence=0.9,
        occurrences=[
            StudioOccurrence(
                segment_id="s1", stable_occurrence_key="o1", snippet="foo baz"
            )
        ],
        review_status=ReviewStatus.accepted,
    )
    rec = StudioReviewRecord(
        session_id="sid",
        generation_id=1,
        candidate_id="c1",
        review_action=ReviewAction.accept,
        review_target_text="qux",
        recorded_at="2026-01-01T00:00:00Z",
        event_sequence=2,
    )
    doc = _doc(candidates=[cand], review_records=[rec])
    svc = _service_with_doc(doc)
    diff = svc.get_candidate_local_diff("sid", "c1")
    assert diff.diffs[0].before == "foo baz"
    assert "qux" in diff.diffs[0].after


@pytest.mark.unit
def test_get_session_stats_counts_unknown_as_pending():
    c1 = StudioCandidate(
        candidate_id="c1",
        generation_id=1,
        kind="k",
        wrong_text="a",
        right_text="b",
        confidence=0.5,
        occurrences=[],
        review_status=ReviewStatus.pending,
    )
    c2 = StudioCandidate(
        candidate_id="c2",
        generation_id=1,
        kind="k",
        wrong_text="a",
        right_text="b",
        confidence=0.5,
        occurrences=[],
        review_status=ReviewStatus.accepted,
    )
    c3 = StudioCandidate(
        candidate_id="c3",
        generation_id=1,
        kind="k",
        wrong_text="a",
        right_text="b",
        confidence=0.5,
        occurrences=[],
        review_status=ReviewStatus.rejected,
    )
    c4 = StudioCandidate(
        candidate_id="c4",
        generation_id=1,
        kind="k",
        wrong_text="a",
        right_text="b",
        confidence=0.5,
        occurrences=[],
        review_status=ReviewStatus.skipped,
    )
    doc = _doc(candidates=[c1, c2, c3, c4])
    svc = _service_with_doc(doc)
    stats = svc.get_session_stats("sid")
    assert (stats.pending, stats.accepted, stats.rejected, stats.skipped) == (
        1,
        1,
        1,
        1,
    )


@pytest.mark.unit
def test_list_transcript_summaries_for_studio_uses_light_picker(
    monkeypatch: pytest.MonkeyPatch,
):
    svc = CorrectionService()

    from transcriptx.core.utils.transcript_picker import TranscriptPickerOption

    monkeypatch.setattr(
        "transcriptx.core.utils.transcript_picker.list_transcript_picker_options",
        lambda: [
            TranscriptPickerOption(path="/tmp/a.json", label="a"),
            TranscriptPickerOption(path="/tmp/a.json", label="a"),
            TranscriptPickerOption(path="/tmp/b.json", label="b"),
        ],
    )

    rows = svc.list_transcript_summaries_for_studio()
    assert [r.path for r in rows] == ["/tmp/a.json", "/tmp/b.json"]
    assert [r.base_name for r in rows] == ["a", "b"]
    assert all(r.segment_count == 0 for r in rows)
