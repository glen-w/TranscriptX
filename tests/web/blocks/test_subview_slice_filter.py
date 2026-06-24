"""Tests for shared subview/slice filter."""

from __future__ import annotations

from dataclasses import dataclass

from transcriptx.web.blocks.filters.subview_slice import (
    discover_slice_ids,
    discover_subviews,
    filter_artifacts_by_subview_slice,
)


@dataclass
class _Art:
    subview: str | None
    slice_id: str | None


def test_discover_subviews_sorted() -> None:
    arts = [_Art("by_speaker", "sp1"), _Art("by_session", "s1"), _Art(None, None)]
    assert discover_subviews(arts) == ["by_session", "by_speaker"]


def test_discover_slice_ids_for_by_speaker() -> None:
    arts = [
        _Art("by_speaker", "alice"),
        _Art("by_speaker", "bob"),
        _Art("by_session", "s1"),
    ]
    assert discover_slice_ids(arts, "by_speaker") == ["alice", "bob"]


def test_filter_artifacts_by_subview_slice() -> None:
    arts = [
        _Art("by_speaker", "alice"),
        _Art("by_speaker", "bob"),
        _Art("by_session", "s1"),
    ]
    filtered = filter_artifacts_by_subview_slice(
        arts, subview="by_speaker", slice_id="alice"
    )
    assert filtered == [_Art("by_speaker", "alice")]
