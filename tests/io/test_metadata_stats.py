"""Tests for transcript document metadata stat resolution."""

from __future__ import annotations

import pytest

from transcriptx.io.metadata_stats import (
    duration_seconds_from_document,
    duration_seconds_from_segments,
    word_count_from_document,
)


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
def test_duration_seconds_from_document_reads_metadata() -> None:
    doc = {"metadata": {"duration_seconds": 99.0}}
    assert duration_seconds_from_document(doc) == 99.0
