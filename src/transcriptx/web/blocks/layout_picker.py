"""Layout profile picker for Overview and Insights."""

from __future__ import annotations

import streamlit as st

from transcriptx.web.blocks.session_context import (
    active_layout_id,
    set_active_layout_id,
)
from transcriptx.web.layouts.store import LayoutProfileStore

_LAYOUT_LABELS = {
    "default": "Standard",
    "executive": "Executive",
    "meeting_followup": "Meeting follow-up",
    "speaker_focus": "Speakers",
    "minimal": "Minimal",
    "developer_debug": "Developer debug",
    "all": "All",
}


def _available_layout_ids(*, include_debug: bool) -> list[str]:
    layouts = LayoutProfileStore.list_layouts()
    if include_debug:
        return layouts
    return [lid for lid in layouts if lid != "developer_debug"]


def render_layout_profile_picker(*, key_prefix: str = "layout") -> None:
    """Select active layout profile; reruns on change."""
    include_debug = bool(st.session_state.get("show_debug_layouts"))
    options = _available_layout_ids(include_debug=include_debug)
    if not options:
        return
    current = active_layout_id()
    if current not in options:
        current = options[0]
    chosen = st.selectbox(
        "Layout",
        options,
        index=options.index(current),
        format_func=lambda lid: _LAYOUT_LABELS.get(lid, lid.replace("_", " ").title()),
        key=f"{key_prefix}_profile_select",
    )
    if chosen != active_layout_id():
        set_active_layout_id(chosen)
        st.rerun()
