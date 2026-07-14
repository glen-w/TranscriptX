"""Unit tests for canonicalization."""

from __future__ import annotations

import pytest

from transcriptx.core.utils.canonicalization import (
    canonicalize_segments,
    compute_source_hash,
    compute_transcript_content_hash,
    compute_transcript_identity_hash,
    normalize_text,
    normalize_timestamp,
)


@pytest.mark.unit
def test_normalize_text_strips_and_normalizes_newlines() -> None:
    text = "  Hello\r\nWorld  \n"
    assert normalize_text(text) == "Hello\nWorld"


@pytest.mark.unit
def test_normalize_timestamp_fixed_decimals() -> None:
    assert normalize_timestamp(1.23456) == "1.235"
    assert normalize_timestamp(1.2, decimals=2) == "1.20"


@pytest.mark.unit
def test_canonicalize_segments_uses_defaults_and_language_fallback() -> None:
    segs = canonicalize_segments(
        [{"text": " Hi ", "speaker": 7}],
        language="en",
    )
    assert len(segs) == 1
    assert segs[0].start == "0.000"
    assert segs[0].end == "0.000"
    assert segs[0].speaker_label == "7"
    assert segs[0].text == "Hi"
    assert segs[0].language == "en"


@pytest.mark.unit
def test_transcript_hash_stable_for_whitespace_changes() -> None:
    segments_a = [
        {"start": 0.0, "end": 1.2345, "speaker": "SPEAKER_00", "text": " Hello world "},
    ]
    segments_b = [
        {"start": 0.0, "end": 1.2345, "speaker": "SPEAKER_00", "text": "Hello world"},
    ]
    assert compute_transcript_content_hash(
        segments_a
    ) == compute_transcript_content_hash(segments_b)


@pytest.mark.unit
def test_transcript_hash_changes_on_text_change() -> None:
    segments_a = [
        {"start": 0.0, "end": 1.2345, "speaker": "SPEAKER_00", "text": "Hello world"},
    ]
    segments_b = [
        {"start": 0.0, "end": 1.2345, "speaker": "SPEAKER_00", "text": "Hello there"},
    ]
    assert compute_transcript_content_hash(
        segments_a
    ) != compute_transcript_content_hash(segments_b)


@pytest.mark.unit
def test_identity_hash_ignores_speaker_but_tracks_text() -> None:
    a = [{"start": 0.0, "end": 1.0, "speaker": "A", "text": "same"}]
    b = [{"start": 0.0, "end": 1.0, "speaker": "B", "text": "same"}]
    c = [{"start": 0.0, "end": 1.0, "speaker": "A", "text": "other"}]
    assert compute_transcript_identity_hash(a) == compute_transcript_identity_hash(b)
    assert compute_transcript_identity_hash(a) != compute_transcript_identity_hash(c)
    assert compute_transcript_identity_hash(a).startswith("sha256:")


@pytest.mark.unit
def test_compute_source_hash_reads_file_bytes(tmp_path) -> None:
    path = tmp_path / "source.bin"
    path.write_bytes(b"abc" * 1000)
    digest = compute_source_hash(str(path))
    assert len(digest) == 64
    assert digest == compute_source_hash(str(path))
