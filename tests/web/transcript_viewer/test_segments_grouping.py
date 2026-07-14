"""Tests for segments grouping."""

from __future__ import annotations

from transcriptx.web.transcript_viewer.segments import group_segments_by_speaker


def test_group_segments_by_speaker_contiguous() -> None:
    grouped = group_segments_by_speaker(
        [
            (0, {"speaker_display": "A", "text": "one"}),
            (1, {"speaker_display": "A", "text": "two"}),
            (2, {"speaker_display": "B", "text": "three"}),
        ]
    )
    assert len(grouped) == 2
    assert grouped[0][0] == "A"
    assert len(grouped[0][1]) == 2
    assert grouped[1][0] == "B"
