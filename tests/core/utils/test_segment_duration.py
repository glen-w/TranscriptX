"""Tests for shared segment duration helper."""

from __future__ import annotations

from transcriptx.core.utils.segment_duration import (
    compute_eligible_speaker_durations,
    valid_segment_duration,
)


def test_valid_segment_duration_rules() -> None:
    assert valid_segment_duration({"start": 0, "end": 2}) == 2.0
    assert valid_segment_duration({"start": 1, "end": 1}) == 0.0
    assert valid_segment_duration({"start": 2, "end": 1}) is None
    assert valid_segment_duration({"start": "x", "end": 1}) is None
    assert valid_segment_duration({"end": 1}) is None
    assert valid_segment_duration({"start": 1}) is None


def test_overlapping_segments_sum_raw_lengths() -> None:
    segments = [
        {"speaker": "Alice", "start": 0.0, "end": 10.0, "text": "a"},
        {"speaker": "Alice", "start": 5.0, "end": 12.0, "text": "b"},
        {"speaker": "Bob", "start": 0.0, "end": 4.0, "text": "c"},
    ]
    result = compute_eligible_speaker_durations(segments)
    assert result.durations["Alice"] == 17.0
    assert result.durations["Bob"] == 4.0
    assert result.total_valid_duration == 21.0


def test_malformed_and_negative_skipped_zero_duration_speaker_kept() -> None:
    segments = [
        {"speaker": "Alice", "start": 0.0, "end": 5.0, "text": "ok"},
        {"speaker": "Alice", "start": "bad", "end": 1.0, "text": "skip"},
        {"speaker": "Bob", "start": 10.0, "end": 8.0, "text": "neg"},
        {"speaker": "Carol", "start": 1.0, "end": 1.0, "text": "zero"},
    ]
    result = compute_eligible_speaker_durations(segments)
    assert result.durations["Alice"] == 5.0
    assert "Bob" in result.eligible_speakers
    assert result.durations["Bob"] == 0.0
    assert result.durations["Carol"] == 0.0
    assert result.skipped_segments >= 2
