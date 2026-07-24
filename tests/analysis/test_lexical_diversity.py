"""Tests for lexical diversity analysis module."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.lexical_diversity import LexicalDiversityAnalysis


def _segments() -> list[dict]:
    return [
        {"speaker": "Alice", "text": "hello world", "start": 0.0, "end": 1.0},
        {"speaker": "Bob", "text": "hello there", "start": 1.0, "end": 2.0},
        {"speaker": "Alice", "text": "again again", "start": 65.0, "end": 66.0},
    ]


@pytest.mark.unit
def test_analyze_speaker_and_global_stats() -> None:
    module = LexicalDiversityAnalysis()
    result = module.analyze(_segments())
    assert "Alice" in result["speaker_stats"]
    assert "Bob" in result["speaker_stats"]
    assert result["global_stats"]["token_count"] > 0
    assert "scores" not in result


@pytest.mark.unit
def test_time_buckets_when_timestamps_present() -> None:
    module = LexicalDiversityAnalysis()
    result = module.analyze(_segments())
    assert len(result["time_buckets"]) >= 2


@pytest.mark.unit
def test_time_buckets_empty_without_timestamps() -> None:
    module = LexicalDiversityAnalysis()
    segments = [{"speaker": "Alice", "text": "hello world"}]
    result = module.analyze(segments)
    assert result["time_buckets"] == []


@pytest.mark.unit
def test_global_uses_eligible_segments_only() -> None:
    module = LexicalDiversityAnalysis()
    segments = [
        {"speaker": "Alice", "text": "alpha beta", "start": 0.0, "end": 1.0},
        {"text": "ignored segment", "start": 1.0, "end": 2.0},
    ]
    result = module.analyze(segments)
    assert result["exclusions"]["skipped_reasons"]["no_speaker"] == 1
    assert result["global_stats"]["token_count"] == 2


@pytest.mark.unit
def test_analyze_keeps_turn_taking_unnamed_in_speaker_stats() -> None:
    """JSON retains diarization labels; charts filter them separately."""
    module = LexicalDiversityAnalysis()
    segments = [
        {"speaker": "Ana", "text": "hello world again", "start": 0.0, "end": 1.0},
        {
            "speaker": "SPEAKER_03",
            "text": "unique rare words only once",
            "start": 1.0,
            "end": 2.0,
        },
    ]
    result = module.analyze(segments)
    assert "Ana" in result["speaker_stats"]
    assert "SPEAKER_03" in result["speaker_stats"]
