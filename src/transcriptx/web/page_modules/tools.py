"""
Tools hub — Workflow → Audio Preprocessing (preprocess and merge).

Uses a segmented control (not ``st.tabs``) so only the active tool panel runs.
"""

from __future__ import annotations

import streamlit as st

from transcriptx.web.navigation import (
    TOOLS_HUB_FORCE_TAB_KEY,
    TOOLS_HUB_TAB_KEY,
    TOOLS_HUB_TABS,
    normalize_tools_hub_tab,
)
from transcriptx.web.ui.tools import (
    render_auto_merge_panel,
    render_dependency_banner,
    render_manual_merge_panel,
    render_preprocess_panel,
)


def render_tools_page() -> None:
    """Render the Tools page (hub with per-tool sections)."""
    st.markdown(
        '<div class="main-header">Audio Preprocessing</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Prepare recordings before external transcription — assess, preprocess, "
        "and merge split files."
    )

    deps_ready = render_dependency_banner()

    tab_labels = list(TOOLS_HUB_TABS)
    force = normalize_tools_hub_tab(st.session_state.pop(TOOLS_HUB_FORCE_TAB_KEY, None))
    if force in tab_labels:
        st.session_state[TOOLS_HUB_TAB_KEY] = force
    else:
        st.session_state[TOOLS_HUB_TAB_KEY] = normalize_tools_hub_tab(
            st.session_state.get(TOOLS_HUB_TAB_KEY)
        )

    label = st.segmented_control(
        "Tool",
        options=tab_labels,
        key=TOOLS_HUB_TAB_KEY,
        label_visibility="collapsed",
    )
    if label not in tab_labels:
        label = tab_labels[0]
        st.session_state[TOOLS_HUB_TAB_KEY] = label

    if label == "Preprocessing":
        render_preprocess_panel(deps_ready=deps_ready)
    elif label == "Auto-merge":
        render_auto_merge_panel(deps_ready=deps_ready)
    elif label == "Manual merge":
        render_manual_merge_panel(deps_ready=deps_ready)
