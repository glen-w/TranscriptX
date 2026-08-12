"""Shared subview and slice filter widgets for Charts and Data pages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

import streamlit as st


class _SubviewArtifact(Protocol):
    subview: str | None
    slice_id: str | None


@dataclass(frozen=True)
class SubviewSliceState:
    subview: str | None
    slice_id: str | None


def discover_subviews(artifacts: Sequence[_SubviewArtifact]) -> list[str]:
    return sorted({a.subview for a in artifacts if a.subview})


def discover_slice_ids(
    artifacts: Sequence[_SubviewArtifact], subview: str
) -> list[str]:
    return sorted(
        {a.slice_id for a in artifacts if a.subview == subview and a.slice_id}
    )


def render_subview_slice_filter(
    artifacts: Sequence[_SubviewArtifact],
    *,
    subview_key: str,
    slice_key: str,
) -> SubviewSliceState:
    """Render subview radio and optional slice selectbox; return filter state."""
    subviews = discover_subviews(artifacts)
    if not subviews:
        return SubviewSliceState(subview=None, slice_id=None)

    tab = st.radio(
        "Subview",
        ["All"] + subviews,
        index=0,
        horizontal=True,
        key=subview_key,
        help="Group rollup vs per-session/per-speaker chart families when both exist.",
    )
    subview = None if tab == "All" else tab
    slice_id: str | None = None
    if subview in {"by_session", "by_speaker"}:
        slice_ids = discover_slice_ids(artifacts, subview)
        if slice_ids:
            slice_choice = st.selectbox(
                "Slice",
                ["All"] + slice_ids,
                index=0,
                key=slice_key,
                help="Focus one session or speaker slice within the selected subview.",
            )
            slice_id = None if slice_choice == "All" else slice_choice
    return SubviewSliceState(subview=subview, slice_id=slice_id)


def filter_artifacts_by_subview_slice(
    artifacts: Sequence[_SubviewArtifact],
    *,
    subview: str | None,
    slice_id: str | None,
) -> list[_SubviewArtifact]:
    if not subview:
        return list(artifacts)
    return [
        a
        for a in artifacts
        if a.subview == subview and (slice_id is None or a.slice_id == slice_id)
    ]
