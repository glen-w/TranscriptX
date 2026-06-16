from __future__ import annotations

from transcriptx.web.transcript_viewer.metadata import (
    segment_word_stats,
    speaker_tooltip,
)


def test_speaker_tooltip_unique_names() -> None:
    tooltip = speaker_tooltip(
        [
            {"speaker_display": "Alice"},
            {"speaker_display": "Bob"},
            {"speaker_display": "Alice"},
            {"speaker": "SPEAKER_00"},
            "invalid",
        ]
    )
    assert tooltip is not None
    assert "- Alice" in tooltip
    assert "- Bob" in tooltip


def test_segment_word_stats_empty() -> None:
    count, words, avg = segment_word_stats([])
    assert count == 0
    assert words == 0
    assert avg == 0.0
