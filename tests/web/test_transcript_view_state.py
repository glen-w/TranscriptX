"""Tests for transcript viewer segment filtering."""

from __future__ import annotations

from transcriptx.web.transcript_view_state import (
    filtered_display_segments,
    segment_has_named_speaker,
)


def test_segment_has_named_speaker_rejects_placeholders() -> None:
    assert segment_has_named_speaker({"speaker": "SPEAKER_02"}) is False
    assert segment_has_named_speaker({"speaker_display": "Alice"}) is True
    assert segment_has_named_speaker({"speaker": "SPEAKER_00", "speaker_display": "Bob"})


def test_filtered_display_segments_excludes_unnamed_by_default() -> None:
    segments = [
        {"speaker": "Alice", "text": "hello"},
        {"speaker": "SPEAKER_02", "text": "subscribe"},
        {"speaker_display": "Bob", "speaker": "SPEAKER_01", "text": "bye"},
    ]
    display, caption = filtered_display_segments(
        segments=segments, search_text="", jump_index=None
    )
    assert [idx for idx, _ in display] == [0, 2]
    assert caption == "Hiding 1 segment from unnamed speakers"


def test_filtered_display_segments_can_include_unnamed() -> None:
    segments = [
        {"speaker": "Alice", "text": "hello"},
        {"speaker": "SPEAKER_02", "text": "subscribe"},
    ]
    display, caption = filtered_display_segments(
        segments=segments,
        search_text="",
        jump_index=None,
        exclude_unnamed_speakers=False,
    )
    assert len(display) == 2
    assert caption is None


def test_filtered_display_segments_keeps_unnamed_jump_target() -> None:
    segments = [
        {"speaker": "Alice", "text": "hello"},
        {"speaker": "SPEAKER_02", "text": "subscribe"},
        {"speaker": "Bob", "text": "bye"},
        {"speaker": "SPEAKER_03", "text": "hidden neighbor"},
    ]
    display, caption = filtered_display_segments(
        segments=segments, search_text="", jump_index=1
    )
    # Full transcript stays visible; unnamed jump target kept, other unnamed dropped.
    assert [idx for idx, _ in display] == [0, 1, 2]
    assert caption == "Hiding 1 segment from unnamed speakers"


def test_filtered_display_segments_jump_does_not_narrow_list() -> None:
    segments = [
        {"speaker": "Alice", "text": f"line {i}"} for i in range(8)
    ]
    display, caption = filtered_display_segments(
        segments=segments, search_text="", jump_index=4
    )
    assert [idx for idx, _ in display] == list(range(8))
    assert caption is None


def test_filtered_display_segments_search_skips_unnamed() -> None:
    segments = [
        {"speaker": "Alice", "text": "please subscribe"},
        {"speaker": "SPEAKER_02", "text": "please subscribe"},
    ]
    display, caption = filtered_display_segments(
        segments=segments, search_text="subscribe", jump_index=None
    )
    assert [idx for idx, _ in display] == [0]
    assert caption == "Showing 1 of 2 segments"
