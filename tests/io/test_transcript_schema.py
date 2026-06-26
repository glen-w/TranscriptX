"""Tests for transcript schema metadata helpers."""

from __future__ import annotations

import pytest

from transcriptx.io.transcript_schema import (
    SourceInfo,
    TranscriptMetadata,
    compute_metadata_from_segments,
    create_transcript_document,
    refresh_document_metadata,
)


@pytest.mark.unit
def test_compute_metadata_from_segments_includes_word_count() -> None:
    segments = [
        {"start": 0.0, "end": 1.0, "speaker": "A", "text": "one two"},
        {"start": 1.0, "end": 2.0, "speaker": "B", "text": "three"},
    ]
    metadata = compute_metadata_from_segments(segments)
    assert metadata.duration_seconds == 2.0
    assert metadata.segment_count == 2
    assert metadata.speaker_count == 2
    assert metadata.word_count == 3


@pytest.mark.unit
def test_compute_metadata_from_segments_span_duration() -> None:
    segments = [
        {"start": 10.0, "end": 12.0, "speaker": "A", "text": "one"},
        {"start": 15.0, "end": 20.0, "speaker": "B", "text": "two"},
    ]
    metadata = compute_metadata_from_segments(segments, duration_calculation="span")
    assert metadata.duration_seconds == 10.0


@pytest.mark.unit
def test_create_transcript_document_writes_word_count() -> None:
    segments = [
        {"start": 0.0, "end": 1.0, "speaker": "A", "text": "hello world"},
    ]
    source = SourceInfo(
        type="manual",
        original_path="/tmp/test.json",
        imported_at="2024-01-01T00:00:00+00:00",
    )
    doc = create_transcript_document(segments, source)
    assert doc["metadata"]["word_count"] == 2


@pytest.mark.unit
def test_create_transcript_document_normalises_word_count_from_segments() -> None:
    segments = [
        {"start": 0.0, "end": 1.0, "speaker": "A", "text": "alpha beta gamma"},
    ]
    source = SourceInfo(
        type="manual",
        original_path="/tmp/test.json",
        imported_at="2024-01-01T00:00:00+00:00",
    )
    metadata = TranscriptMetadata(
        duration_seconds=1.0,
        segment_count=1,
        speaker_count=1,
        word_count=0,
    )
    doc = create_transcript_document(segments, source, metadata)
    assert doc["metadata"]["word_count"] == 3
    assert doc["metadata"]["duration_seconds"] == 1.0


@pytest.mark.unit
def test_refresh_document_metadata_preserves_custom_fields() -> None:
    doc = {
        "schema_version": "1.0",
        "metadata": {
            "title": "Meeting notes",
            "language": "en",
            "duration_seconds": 1.0,
            "segment_count": 1,
            "speaker_count": 1,
            "word_count": 1,
        },
        "segments": [
            {"start": 0.0, "end": 2.0, "speaker": "A", "text": "one two three four"},
        ],
    }
    refresh_document_metadata(doc)
    assert doc["metadata"]["title"] == "Meeting notes"
    assert doc["metadata"]["language"] == "en"
    assert doc["metadata"]["word_count"] == 4
    assert doc["metadata"]["duration_seconds"] == 2.0
    assert doc["metadata"]["segment_count"] == 1
