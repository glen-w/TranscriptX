"""Tests for transcript page speakers tooltip."""

from __future__ import annotations


def test_transcript_page_speakers_metric_has_help_tooltip(monkeypatch) -> None:
    from transcriptx.web.transcript_viewer.metadata import speaker_tooltip

    segments = [
        {"speaker": "SPEAKER_00", "speaker_display": "Alice"},
        {"speaker": "SPEAKER_01", "speaker_display": "Bob"},
        {"speaker": "SPEAKER_02", "speaker_display": "Alice"},
    ]
    help_text = speaker_tooltip(segments)
    assert help_text is not None
    assert "- Alice" in help_text
    assert "- Bob" in help_text
