"""Tests for transcript document metadata stat resolution."""

from __future__ import annotations

import pytest

from transcriptx.io.metadata_display_options import get_metadata_config
from transcriptx.io.metadata_stats import (
    DEFAULT_SESSION_STATS,
    duration_seconds_from_document,
    duration_seconds_from_segments,
    listing_stats_from_document,
    optional_span_duration_seconds_from_segments,
    word_count_from_document,
)


class TestListingStatsFromDocument:

    def test_canonical_metadata(self) -> None:
        doc = {
            "metadata": {
                "segment_count": 120,
                "duration_seconds": 3600.0,
                "speaker_count": 3,
                "word_count": 42,
            }
        }
        stats = listing_stats_from_document(doc, meta_cfg=get_metadata_config())
        assert stats["segment_count"] == 120
        assert stats["duration_seconds"] == 3600.0
        assert stats["duration_minutes"] == 60.0
        assert stats["speaker_count"] == 3
        assert stats["word_count"] == 42

    def test_legacy_words_alias(self) -> None:
        doc = {"metadata": {"words": 99}}
        stats = listing_stats_from_document(doc, meta_cfg=get_metadata_config())
        assert stats["word_count"] == 99

    def test_segment_fallback_when_metadata_lacks_word_count(self) -> None:
        doc = {
            "metadata": {"segment_count": 2},
            "segments": [
                {"text": "one two three"},
                {"text": "four five"},
            ],
        }
        stats = listing_stats_from_document(doc, meta_cfg=get_metadata_config())
        assert stats["word_count"] == 5

    def test_legacy_metadata_keys(self) -> None:
        doc = {
            "metadata": {
                "segments": 50,
                "duration": 120.0,
                "num_speakers": 2,
            }
        }
        stats = listing_stats_from_document(doc, meta_cfg=get_metadata_config())
        assert stats["segment_count"] == 50
        assert stats["duration_seconds"] == 120.0
        assert stats["duration_minutes"] == 2.0
        assert stats["speaker_count"] == 2
        assert stats["word_count"] == 0

    def test_missing_metadata_returns_defaults(self) -> None:
        cfg = get_metadata_config()
        assert listing_stats_from_document({}, meta_cfg=cfg) == dict(
            DEFAULT_SESSION_STATS
        )
        assert listing_stats_from_document({"metadata": "bad"}, meta_cfg=cfg) == dict(
            DEFAULT_SESSION_STATS
        )

    def test_partial_metadata_merges_with_defaults(self) -> None:
        stats = listing_stats_from_document(
            {"metadata": {"segment_count": 10}},
            meta_cfg=get_metadata_config(),
        )
        assert stats["segment_count"] == 10
        assert stats["duration_seconds"] == 0
        assert stats["speaker_count"] == 0
        assert stats["word_count"] == 0


@pytest.mark.unit
def test_word_count_from_document_prefers_metadata() -> None:
    doc = {"metadata": {"word_count": 10}, "segments": [{"text": "one two three"}]}
    assert word_count_from_document(doc) == 10


@pytest.mark.unit
def test_word_count_from_document_legacy_words_alias() -> None:
    doc = {"metadata": {"words": 7}}
    assert word_count_from_document(doc) == 7


@pytest.mark.unit
def test_word_count_from_document_segment_fallback() -> None:
    doc = {
        "metadata": {},
        "segments": [{"text": "one two"}, {"text": "three"}],
    }
    assert word_count_from_document(doc) == 3


@pytest.mark.unit
def test_word_count_from_document_metadata_only_mode() -> None:
    doc = {
        "metadata": {},
        "segments": [{"text": "one two three"}],
    }
    assert word_count_from_document(doc, allow_segment_fallback=False) == 0


@pytest.mark.unit
def test_duration_seconds_from_segments_span() -> None:
    segments = [
        {"start": 10.0, "end": 12.0},
        {"start": 15.0, "end": 20.0},
    ]
    assert duration_seconds_from_segments(segments, method="max_end") == 20.0
    assert duration_seconds_from_segments(segments, method="span") == 10.0


@pytest.mark.unit
def test_optional_span_duration_differs_from_max_end() -> None:
    segments = [
        {"start": 1.0, "end": 3.0, "speaker": "S1"},
        {"start": 4.0, "end": 8.5, "speaker": "S2"},
    ]
    assert optional_span_duration_seconds_from_segments(segments) == 7.5
    assert duration_seconds_from_segments(segments, method="max_end") == 8.5


@pytest.mark.unit
def test_optional_span_duration_returns_none_for_invalid_pairs() -> None:
    segments = [
        {"start": None, "end": 3.0, "speaker": "S1"},
        {"start": 10.0, "end": 2.0, "speaker": "S2"},
        {"start": "bad", "end": "data", "speaker": None},
    ]
    assert optional_span_duration_seconds_from_segments(segments) is None


@pytest.mark.unit
def test_duration_seconds_from_document_reads_metadata() -> None:
    doc = {"metadata": {"duration_seconds": 99.0}}
    assert duration_seconds_from_document(doc) == 99.0
