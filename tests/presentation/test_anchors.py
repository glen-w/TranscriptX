"""Tests for anchor formatting helpers."""

from __future__ import annotations

import pytest

from transcriptx.core.presentation.anchors import (
    format_segment_anchor,
    format_segment_anchor_md,
    format_timecode,
)


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, "--"),
        ("bad", "--"),
        (61.2, "1:01"),
    ],
)
def test_format_timecode(value: object, expected: str) -> None:
    assert format_timecode(value) == expected


@pytest.mark.parametrize(
    "indexes, expected",
    [
        ([3], "seg#3"),
        ([3, 7], "seg#3-7"),
    ],
)
def test_segment_index_preference(indexes: list[int], expected: str) -> None:
    anchor = format_segment_anchor(
        start=10,
        end=15,
        speaker="Emma",
        segment_indexes=indexes,
        segment_db_ids=[99],
        segment_uuids=["uuid"],
    )
    assert expected in anchor
    assert "Emma" in anchor


def test_segment_db_id_fallback() -> None:
    anchor = format_segment_anchor(
        start=1,
        end=2,
        speaker="Sam",
        segment_indexes=[],
        segment_db_ids=[10, 11],
        segment_uuids=[],
    )
    assert "db#10+1" in anchor


def test_segment_uuid_fallback() -> None:
    anchor = format_segment_anchor(
        start=None,
        end=None,
        speaker=None,
        segment_indexes=None,
        segment_db_ids=None,
        segment_uuids=["abcdef123456"],
    )
    assert "uuid#abcdef12" in anchor


def test_anchor_markdown_wrapper() -> None:
    anchor_md = format_segment_anchor_md(
        start=0,
        end=1,
        speaker="Dana",
        segment_indexes=[4],
    )
    assert anchor_md.startswith("[")
    assert anchor_md.endswith("]")
