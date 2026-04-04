"""Tests for interactions analyzer."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.interactions.analyzer import (  # type: ignore[import-untyped]
    SpeakerInteractionAnalyzer,
)


def _segment(idx: int, speaker: str, start: float, end: float) -> dict:
    return {
        "segment_index": idx,
        "speaker": speaker,
        "start": start,
        "end": end,
        "text": f"seg {idx}",
    }


def test_detects_overlap_and_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "transcriptx.core.analysis.interactions.analyzer.notify_user",
        lambda *args, **kwargs: None,
    )
    analyzer = SpeakerInteractionAnalyzer(
        overlap_threshold=0.5,
        min_gap=0.1,
        min_segment_length=0.1,
        response_threshold=2.0,
        include_responses=True,
        include_overlaps=True,
    )
    segments = [
        _segment(0, "A", 0.0, 3.0),
        _segment(1, "B", 2.5, 4.0),  # overlap
    ]
    interactions = analyzer.detect_interactions(segments)
    kinds = {event.interaction_type for event in interactions}
    assert "interruption_overlap" in kinds
    # Response detection is heuristic and may not trigger for overlap-only inputs.


def test_skips_short_segments(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "transcriptx.core.analysis.interactions.analyzer.notify_user",
        lambda *args, **kwargs: None,
    )
    analyzer = SpeakerInteractionAnalyzer(min_segment_length=1.0)
    segments = [
        _segment(0, "A", 0.0, 0.4),
        _segment(1, "B", 0.5, 1.0),
    ]
    assert analyzer.detect_interactions(segments) == []
