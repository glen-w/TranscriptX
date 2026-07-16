"""Unit tests for export contiguous speaker grouping (0.3.5)."""

from __future__ import annotations

import pytest

from transcriptx.export.grouping import (
    group_contiguous_segments_by_speaker,
    segment_speaker_label,
)


@pytest.mark.unit
def test_segment_speaker_label_precedence() -> None:
    assert (
        segment_speaker_label({"speaker_display": "Alice", "speaker": "S0"}) == "Alice"
    )
    assert segment_speaker_label({"speaker": "S0"}) == "S0"
    assert segment_speaker_label({}) == "Unknown"


@pytest.mark.unit
def test_group_contiguous_skips_non_dict_and_splits_speakers() -> None:
    segments = [
        {"speaker": "A", "text": "1"},
        "skip",
        {"speaker": "A", "text": "2"},
        {"speaker": "B", "text": "3"},
        {"speaker_display": "B", "speaker": "S1", "text": "4"},
    ]
    groups = group_contiguous_segments_by_speaker(segments)
    assert [speaker for speaker, _ in groups] == ["A", "B"]
    assert len(groups[0][1]) == 2
    assert len(groups[1][1]) == 2
