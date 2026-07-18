"""Streamlit sidebar workspace pickers and status captions."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import streamlit as st

from transcriptx.web.sidebar_hydration import SidebarStatus
from transcriptx.web.state import (
    RUN_SELECTOR_KEY,
    SELECTBOX_PLACEHOLDER_GROUP,
    SELECTBOX_PLACEHOLDER_TRANSCRIPT,
    SUBJECT_ID_SELECTOR_KEY,
)


def _selectbox_index_kwargs(
    *,
    key: str,
    options: list[str],
    preferred: str | None,
    fallback_index: int = 0,
) -> dict[str, int]:
    """Return ``index=`` only when the widget key is not already in session state.

    ``apply_subject_context`` (and similar navigators) write keyed picker values
    before the sidebar renders. Passing both that value and ``index`` triggers
    Streamlit's widget-state duplication warning; session state wins, so omit
    ``index`` when the key is already set. If the stored value is stale relative
    to current options, rewrite it before the widget instantiates.
    """
    if key in st.session_state:
        current = st.session_state.get(key)
        if current not in options:
            st.session_state[key] = (
                preferred if preferred in options else options[fallback_index]
            )
        return {}
    if preferred and preferred in options:
        return {"index": options.index(preferred)}
    return {"index": fallback_index}


def render_sidebar_stats(
    *,
    status: SidebarStatus,
    subject_type: str,
) -> None:
    """Render workspace status captions for loading/empty lists."""
    if status == "loading":
        st.caption("Workspace list loading...")
        return
    if status == "empty":
        if subject_type == "group":
            st.caption("No groups yet")
        else:
            st.caption("No transcripts yet")


def render_no_runs_hint(*, subject_type: str) -> None:
    """Hint when a subject is selected but has no analysis runs."""
    noun = "group" if subject_type == "group" else "transcript"
    st.caption(f"No runs for this {noun} yet — open Run Analysis to create one.")


def render_transcript_picker(
    *,
    options: list[str],
    format_func: Callable[[str], str],
    default_subject_id: str | None,
) -> str | None:
    """Render transcript selectbox; return selected slug or None for placeholder."""
    choices = [""] + options
    selected = st.selectbox(
        "Transcript",
        choices,
        format_func=lambda x: (
            SELECTBOX_PLACEHOLDER_TRANSCRIPT if x == "" else format_func(x)
        ),
        key=SUBJECT_ID_SELECTOR_KEY,
        label_visibility="collapsed",
        **_selectbox_index_kwargs(
            key=SUBJECT_ID_SELECTOR_KEY,
            options=choices,
            preferred=default_subject_id,
        ),
    )
    return selected if selected else None


def render_group_picker(
    *,
    group_keys: list[str],
    group_labels: dict[str, str],
    default_subject_id: str | None,
) -> str | None:
    """Render group selectbox; return selected group uuid or None for placeholder."""
    choices = [""] + group_keys
    selected_group = st.selectbox(
        "Group",
        choices,
        format_func=lambda key: (
            SELECTBOX_PLACEHOLDER_GROUP if key == "" else group_labels.get(key, key)
        ),
        key=SUBJECT_ID_SELECTOR_KEY,
        label_visibility="collapsed",
        **_selectbox_index_kwargs(
            key=SUBJECT_ID_SELECTOR_KEY,
            options=choices,
            preferred=default_subject_id,
        ),
    )
    return selected_group if selected_group else None


def render_run_picker(
    *,
    run_options: list[str],
    default_run_id: str | None,
) -> str:
    """Render run selectbox; return selected run id."""
    return st.selectbox(
        "Run",
        run_options,
        key=RUN_SELECTOR_KEY,
        **_selectbox_index_kwargs(
            key=RUN_SELECTOR_KEY,
            options=run_options,
            preferred=default_run_id,
        ),
    )


def build_group_labels(groups: list[Any]) -> dict[str, str]:
    """Build group uuid -> display label map."""
    return {
        g.uuid: f"{g.name or 'Unnamed'} • {len(g.transcript_file_uuids or [])} transcripts"
        for g in groups
    }
