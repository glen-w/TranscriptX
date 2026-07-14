"""Tests for transcript page segments tooltip."""

from __future__ import annotations


def test_transcript_page_segments_metric_has_words_tooltip() -> None:
    from transcriptx.web.transcript_viewer.metadata import segment_word_stats

    segments = [{"text": "hello world"}, {"text": "one two three four"}]
    count, total_words, avg_words = segment_word_stats(segments)
    help_text = f"Total words: {total_words:,}\nAverage words/segment: {avg_words:.1f}"

    assert count == 2
    assert "Total words: 6" in help_text
    assert "Average words/segment: 3.0" in help_text
