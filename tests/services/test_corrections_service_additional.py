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


@pytest.mark.unit
def test_get_candidate_local_diff_returns_empty_when_candidate_missing():
    doc = SimpleNamespace(candidates=[], review_records=[], current_generation_id=1)
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
    doc = SimpleNamespace(
        candidates=[cand], review_records=[rec], current_generation_id=1
    )
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
    doc = SimpleNamespace(
        candidates=[c1, c2, c3, c4], review_records=[], current_generation_id=1
    )
    svc = _service_with_doc(doc)
    stats = svc.get_session_stats("sid")
    assert (stats.pending, stats.accepted, stats.rejected, stats.skipped) == (
        1,
        1,
        1,
        1,
    )


@pytest.mark.unit
def test_list_transcript_summaries_for_studio_fallback_and_dedupe(
    monkeypatch: pytest.MonkeyPatch,
):
    svc = CorrectionService()

    monkeypatch.setattr(
        "transcriptx.core.utils.file_discovery.discover_managed_transcript_paths",
        lambda _x: ["/tmp/a.json", "/tmp/a.json"],
    )

    class _Idx:
        def summary_for_path(self, p):
            return None

        def list_transcripts(self, canonical_only=False):
            return [
                SimpleNamespace(
                    path="/tmp/a.json",
                    base_name="a",
                    segment_count=3,
                    speaker_map_status="present",
                ),
                SimpleNamespace(
                    path="/tmp/a.json",
                    base_name="a",
                    segment_count=3,
                    speaker_map_status="present",
                ),
                SimpleNamespace(
                    path="/tmp/b.json",
                    base_name="b",
                    segment_count=4,
                    speaker_map_status="missing",
                ),
            ]

    monkeypatch.setattr(
        "transcriptx.services.speaker_studio.segment_index.SegmentIndexService",
        _Idx,
    )

    rows = svc.list_transcript_summaries_for_studio()
    assert [r.path for r in rows] == ["/tmp/a.json", "/tmp/b.json"]
