"""Tests for Transcript playback target construction and view signatures."""

from __future__ import annotations

import math

from transcriptx.web.transcript_viewer.playback_targets import (
    CLIP_DURATION_CAP_SEC,
    build_playback_targets,
    coerce_playback_timestamp,
    filtered_view_signature,
    ordered_playback_targets,
    segment_playback_speaker,
    warm_list_position,
)


def test_speaker_fallback_chain() -> None:
    assert segment_playback_speaker({"speaker_display": "Alice", "speaker": "S0"}) == (
        "Alice"
    )
    assert segment_playback_speaker({"speaker": "SPEAKER_00"}) == "SPEAKER_00"
    assert segment_playback_speaker({}) == "Unknown"
    assert segment_playback_speaker({"speaker_display": "  ", "speaker": ""}) == (
        "Unknown"
    )


def test_timestamp_coercion_rejects_invalid() -> None:
    assert coerce_playback_timestamp(1.5) == 1.5
    assert coerce_playback_timestamp("2.25") == 2.25
    assert coerce_playback_timestamp(True) is None
    assert coerce_playback_timestamp(False) is None
    assert coerce_playback_timestamp(None) is None
    assert coerce_playback_timestamp("nope") is None
    assert coerce_playback_timestamp(math.nan) is None
    assert coerce_playback_timestamp(math.inf) is None


def test_build_playback_targets_uses_source_index_and_skips_invalid() -> None:
    display = [
        (0, {"start": 0.0, "end": 1.0, "text": "a", "speaker": "A"}),
        (3, {"start": True, "end": 2.0, "text": "bad bool"}),
        (5, {"start": 2.0, "end": 2.0, "text": "zero dur"}),
        (7, {"start": 10.0, "end": -1.0, "text": "neg end"}),
        (9, {"start": 1.0, "end": 90.0, "text": "long", "speaker_display": "Bob"}),
    ]
    targets = build_playback_targets(display)
    assert set(targets) == {0, 9}
    assert targets[0].index == 0
    assert targets[0].speaker == "A"
    assert targets[9].index == 9
    assert targets[9].speaker == "Bob"
    assert targets[9].end - targets[9].start > CLIP_DURATION_CAP_SEC


def test_ordered_targets_follow_filtered_display_not_source_order() -> None:
    display = [
        (5, {"start": 5.0, "end": 6.0, "text": "five"}),
        (1, {"start": 1.0, "end": 2.0, "text": "one"}),
    ]
    targets = build_playback_targets(display)
    ordered = ordered_playback_targets(display, targets)
    assert [t.index for t in ordered] == [5, 1]


def test_search_filtered_play_uses_original_source_index() -> None:
    """Playing filtered ordinal 0 must address source index 4, not transcript[0]."""
    full = [
        (0, {"start": 0.0, "end": 1.0, "text": "skip me"}),
        (4, {"start": 4.0, "end": 5.0, "text": "hit"}),
    ]
    filtered = [full[1]]
    targets = build_playback_targets(filtered)
    assert list(targets) == [4]
    assert targets[4].text == "hit"
    assert targets[4].start == 4.0


def test_jump_filtered_play_uses_original_source_index() -> None:
    context = [
        (2, {"start": 2.0, "end": 3.0, "text": "a"}),
        (3, {"start": 3.0, "end": 4.0, "text": "b"}),
        (4, {"start": 4.0, "end": 5.0, "text": "c"}),
    ]
    targets = build_playback_targets(context)
    assert set(targets) == {2, 3, 4}
    assert targets[3].text == "b"


def test_filtered_view_signature_stable_and_sensitive() -> None:
    owner = ("slug", "run1", "/tmp/a.json", 1, 2)
    segs_a = [(0, {"start": 0.0, "end": 1.0}), (2, {"start": 2.0, "end": 3.0})]
    segs_b = [(0, {"start": 0.0, "end": 1.0})]
    sig_a = filtered_view_signature(owner_identity=owner, display_segments=segs_a)
    sig_a2 = filtered_view_signature(owner_identity=owner, display_segments=segs_a)
    sig_b = filtered_view_signature(owner_identity=owner, display_segments=segs_b)
    sig_other_owner = filtered_view_signature(
        owner_identity=("slug", "run2", "/tmp/a.json", 1, 2),
        display_segments=segs_a,
    )
    assert sig_a == sig_a2
    assert sig_a != sig_b
    assert sig_a != sig_other_owner


def test_filtered_view_signature_includes_search_and_jump() -> None:
    owner = ("slug", "run1", "/tmp/a.json", 1, 2)
    segs = [(0, {"start": 0.0, "end": 1.0}), (2, {"start": 2.0, "end": 3.0})]
    base = filtered_view_signature(owner_identity=owner, display_segments=segs)
    by_search = filtered_view_signature(
        owner_identity=owner, display_segments=segs, search_text="hello"
    )
    by_other_search = filtered_view_signature(
        owner_identity=owner, display_segments=segs, search_text="world"
    )
    by_jump = filtered_view_signature(
        owner_identity=owner, display_segments=segs, jump_index=2
    )
    assert base != by_search
    assert by_search != by_other_search
    assert base != by_jump


def test_warm_list_position_maps_source_index() -> None:
    display = [
        (2, {"start": 2.0, "end": 3.0, "text": "a"}),
        (5, {"start": 5.0, "end": 6.0, "text": "b"}),
    ]
    ordered = ordered_playback_targets(display, build_playback_targets(display))
    assert warm_list_position(ordered, 5) == 1
    assert warm_list_position(ordered, 99) is None
    assert warm_list_position(ordered, None) is None
    assert warm_list_position(ordered, True) is None  # type: ignore[arg-type]


def test_group_timestamp_bounds_uses_valid_finite_only() -> None:
    from transcriptx.web.transcript_viewer.playback_targets import (
        group_timestamp_bounds,
    )

    bounds = group_timestamp_bounds(
        [
            (0, {"start": None, "end": 1.0}),
            (1, {"start": 2.0, "end": "bad"}),
            (2, {"start": 3.0, "end": 4.5}),
            (3, {"start": 5.0, "end": 6.0}),
        ]
    )
    assert bounds == (3.0, 6.0)
    assert group_timestamp_bounds([(0, {"start": None, "end": None})]) is None
    # Independent start/end from different malformed segments must not fabricate.
    assert (
        group_timestamp_bounds(
            [
                (0, {"start": 10.0, "end": None}),
                (1, {"start": None, "end": 1.0}),
            ]
        )
        is None
    )


def test_format_safe_timestamp_range_omits_invalid() -> None:
    from transcriptx.web.transcript_viewer.playback_targets import (
        format_safe_timestamp_range,
    )

    def _fmt(seconds: float, _key: str) -> str:
        return f"{seconds:.1f}s"

    assert format_safe_timestamp_range(1.0, 2.0, "seconds", format_single=_fmt) == (
        "1.0s - 2.0s"
    )
    assert format_safe_timestamp_range(None, 2.0, "seconds", format_single=_fmt) is None
    assert (
        format_safe_timestamp_range(1.0, math.nan, "seconds", format_single=_fmt)
        is None
    )
    assert format_safe_timestamp_range(2.0, 1.0, "seconds", format_single=_fmt) is None
    assert format_safe_timestamp_range(1.0, -1.0, "seconds", format_single=_fmt) is None
