"""Deterministic rename preview clip selection."""

from __future__ import annotations

import pytest

from transcriptx.services.speaker_studio.segment_index import SegmentInfo
from transcriptx.web.services.rename_preview_clips import (
    UNKNOWN_SPEAKER_LABEL,
    effective_rename_speaker_label,
    mapped_speaker_summary_labels,
    select_rename_preview_segments,
    speaker_identity_key,
)


def _seg(
    index: int,
    start: float,
    end: float,
    text: str,
    *,
    speaker: str = "SPEAKER_00",
    diarized: str | None = None,
) -> SegmentInfo:
    return SegmentInfo(
        index=index,
        start=start,
        end=end,
        text=text,
        speaker=speaker,
        speaker_diarized_id=diarized,
    )


@pytest.mark.unit
def test_selection_is_deterministic() -> None:
    segs = [
        _seg(i, float(i), float(i) + 1.0, f"line {i}", speaker=f"SPEAKER_{i % 3:02d}")
        for i in range(30)
    ]
    a = select_rename_preview_segments(segs, limit=10)
    b = select_rename_preview_segments(list(reversed(segs)), limit=10)
    # Input order must not matter: rebuild from same segments yields same pick.
    c = select_rename_preview_segments(segs, limit=10)
    assert [s.index for s in a] == [s.index for s in c]
    assert len(a) == 10
    # reversed list still contains same SegmentInfo objects → same selection
    assert [s.index for s in a] == [s.index for s in b]


@pytest.mark.unit
def test_groups_by_diarized_id_not_display_name() -> None:
    segs = [
        _seg(0, 0.0, 1.0, "a", speaker="Alice", diarized="SPEAKER_00"),
        _seg(1, 1.0, 2.0, "b", speaker="Alice", diarized="SPEAKER_01"),
        _seg(2, 2.0, 3.0, "c", speaker="Alice", diarized="SPEAKER_00"),
        _seg(3, 3.0, 4.0, "d", speaker="Alice", diarized="SPEAKER_01"),
    ]
    assert speaker_identity_key(segs[0]) != speaker_identity_key(segs[1])
    picked = select_rename_preview_segments(segs, limit=2)
    keys = {speaker_identity_key(s) for s in picked}
    assert keys == {"SPEAKER_00", "SPEAKER_01"}


@pytest.mark.unit
def test_even_spacing_one_and_two_segments() -> None:
    one = [_seg(0, 0.0, 1.0, "only")]
    assert [s.index for s in select_rename_preview_segments(one, limit=10)] == [0]

    two = [
        _seg(0, 0.0, 1.0, "first"),
        _seg(1, 1.0, 2.0, "second"),
    ]
    assert len(select_rename_preview_segments(two, limit=10)) == 2
    assert [s.index for s in select_rename_preview_segments(two, limit=1)] == [1]


@pytest.mark.unit
def test_more_than_ten_speakers_takes_first_ten_by_order() -> None:
    segs = [
        _seg(i, float(i), float(i) + 0.5, f"t{i}", speaker=f"SPEAKER_{i:02d}")
        for i in range(12)
    ]
    picked = select_rename_preview_segments(segs, limit=10)
    assert len(picked) == 10
    keys = [speaker_identity_key(s) for s in picked]
    assert keys == [f"SPEAKER_{i:02d}" for i in range(10)]


@pytest.mark.unit
def test_duplicate_text_backfills_from_remaining() -> None:
    # Primary would pick duplicates; backfill should fill to 3 unique texts.
    segs = [
        _seg(0, 0.0, 1.0, "same", speaker="SPEAKER_00"),
        _seg(1, 1.0, 2.0, "same", speaker="SPEAKER_00"),
        _seg(2, 2.0, 3.0, "same", speaker="SPEAKER_00"),
        _seg(3, 3.0, 4.0, "other", speaker="SPEAKER_01"),
        _seg(4, 4.0, 5.0, "third", speaker="SPEAKER_02"),
    ]
    picked = select_rename_preview_segments(segs, limit=3)
    texts = sorted(_normalize(s.text) for s in picked)
    assert texts == ["other", "same", "third"]
    assert len(picked) == 3


def _normalize(text: str) -> str:
    return " ".join(text.strip().casefold().split())


@pytest.mark.unit
def test_fewer_than_limit_returns_all_eligible() -> None:
    segs = [
        _seg(0, 0.0, 1.0, "a"),
        _seg(1, 1.0, 2.0, ""),  # ineligible
        _seg(2, 3.0, 2.0, "bad timing"),  # ineligible
    ]
    picked = select_rename_preview_segments(segs, limit=10)
    assert [s.index for s in picked] == [0]


@pytest.mark.unit
def test_speaker_label_fallback_chain() -> None:
    mapped = _seg(0, 0.0, 1.0, "hi", speaker="Alice", diarized="SPEAKER_00")
    assert effective_rename_speaker_label(mapped) == "Alice"

    diarized = _seg(1, 1.0, 2.0, "hi", speaker="SPEAKER_01")
    assert effective_rename_speaker_label(diarized) == "SPEAKER_01"

    missing = _seg(2, 2.0, 3.0, "hi", speaker="", diarized=None)
    missing.speaker = ""
    assert effective_rename_speaker_label(missing) == UNKNOWN_SPEAKER_LABEL


@pytest.mark.unit
def test_mapped_summary_uses_same_segment_set() -> None:
    segs = [
        _seg(0, 0.0, 1.0, "a", speaker="Alice", diarized="SPEAKER_00"),
        _seg(1, 1.0, 2.0, "b", speaker="Bob", diarized="SPEAKER_01"),
        _seg(2, 2.0, 3.0, "c", speaker="SPEAKER_02"),
    ]
    preview = select_rename_preview_segments(segs, limit=10)
    assert mapped_speaker_summary_labels(preview) == ["Alice", "Bob"]
