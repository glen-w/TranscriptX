"""Streamlit sidebar workspace pickers and status captions."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import streamlit as st

from transcriptx.web.sidebar_hydration import SidebarStatus
from transcriptx.web.state import (
    SELECTBOX_PLACEHOLDER_GROUP,
    SELECTBOX_PLACEHOLDER_TRANSCRIPT,
)


def render_sidebar_stats(
    *,
    status: SidebarStatus,
    subject_type: str,
    show_no_selection: bool = False,
) -> None:
    """Render existing workspace status captions verbatim."""
    if show_no_selection:
        st.caption("No transcript selected")
        return
    if status == "loading":
        st.caption("Workspace list loading...")
        return
    if status == "empty":
        if subject_type == "group":
            st.caption("No groups yet")
        else:
            st.caption("No transcripts yet")


def render_transcript_picker(
    *,
    options: list[str],
    format_func: Callable[[str], str],
    default_subject_id: str | None,
) -> str | None:
    """Render transcript selectbox; return selected slug or None for placeholder."""
    default_idx = 0
    if default_subject_id and default_subject_id in options:
        default_idx = options.index(default_subject_id) + 1
    selected = st.selectbox(
        "Transcript",
        [""] + options,
        format_func=lambda x: (
            SELECTBOX_PLACEHOLDER_TRANSCRIPT if x == "" else format_func(x)
        ),
        index=default_idx,
        key="subject_id_selector",
    )
    return selected if selected else None


def render_group_picker(
    *,
    group_keys: list[str],
    group_labels: dict[str, str],
    default_subject_id: str | None,
) -> str | None:
    """Render group selectbox; return selected group uuid or None for placeholder."""
    default_idx = 0
    if default_subject_id and default_subject_id in group_keys:
        default_idx = group_keys.index(default_subject_id) + 1
    selected_group = st.selectbox(
        "Group",
        [""] + group_keys,
        format_func=lambda key: (
            SELECTBOX_PLACEHOLDER_GROUP if key == "" else group_labels.get(key, key)
        ),
        index=default_idx,
        key="subject_id_selector",
    )
    return selected_group if selected_group else None


def render_run_picker(
    *,
    run_options: list[str],
    default_run_id: str | None,
) -> str:
    """Render run selectbox; return selected run id."""
    index = run_options.index(default_run_id) if default_run_id in run_options else 0
    return st.selectbox(
        "Run",
        run_options,
        index=index,
        key="run_selector",
    )


def build_group_labels(groups: list[Any]) -> dict[str, str]:
    """Build group uuid -> display label map."""
    return {
        g.uuid: f"{g.name or 'Unnamed'} • {len(g.transcript_file_uuids or [])} transcripts"
        for g in groups
    }
