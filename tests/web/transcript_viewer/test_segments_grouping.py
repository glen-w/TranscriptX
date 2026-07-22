"""Tests for Turns grouping with preserved source indices."""

from __future__ import annotations

from transcriptx.web.transcript_viewer.segments import (
    TranscriptPlaybackBinding,
    group_segments_by_speaker,
    play_button_eligible,
    play_button_key,
)
from transcriptx.services.speaker_studio.segment_index import SegmentInfo


def test_group_segments_by_speaker_contiguous_preserves_indices() -> None:
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
    assert grouped[0][1][0][0] == 0
    assert grouped[0][1][1][0] == 1
    assert grouped[1][0] == "B"
    assert grouped[1][1][0][0] == 2


def test_group_segments_retains_noncontiguous_source_indices() -> None:
    grouped = group_segments_by_speaker(
        [
            (2, {"speaker_display": "A", "text": "a"}),
            (7, {"speaker_display": "A", "text": "b"}),
            (9, {"speaker_display": "B", "text": "c"}),
            (11, {"speaker_display": "A", "text": "d"}),
        ]
    )
    assert [g[0] for g in grouped] == ["A", "B", "A"]
    assert [idx for idx, _ in grouped[0][1]] == [2, 7]
    assert [idx for idx, _ in grouped[1][1]] == [9]
    assert [idx for idx, _ in grouped[2][1]] == [11]


def test_play_button_keys_distinct_across_tabs() -> None:
    binding = TranscriptPlaybackBinding(
        enabled=True,
        targets={
            3: SegmentInfo(index=3, start=1.0, end=2.0, text="x", speaker="A"),
        },
        play_key="transcript_viewer_play_seg",
        owner_prefix="abcd1234efgh5678",
    )
    turns_key = play_button_key(binding, "turns", 3)
    segments_key = play_button_key(binding, "segments", 3)
    assert turns_key != segments_key
    assert "turns" in turns_key
    assert "segments" in segments_key
    assert "|3" in turns_key
    assert len(binding.owner_prefix) == 16
    assert "transcript_copy_visible_txt" not in turns_key
