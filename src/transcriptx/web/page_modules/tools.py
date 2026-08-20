"""
Tools hub — Workflow → Audio Preprocessing (preprocess and merge).
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
    """Render the Tools page (hub with per-tool tabs)."""
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
    # One-shot reorder so legacy redirects / handoffs land on the intended tab.
    # Streamlit always opens the first tab visually and runs every tab body.
    force = normalize_tools_hub_tab(st.session_state.pop(TOOLS_HUB_FORCE_TAB_KEY, None))
    if force in tab_labels and force != tab_labels[0]:
        tab_labels = [force] + [t for t in tab_labels if t != force]
        st.session_state[TOOLS_HUB_TAB_KEY] = force
    else:
        st.session_state[TOOLS_HUB_TAB_KEY] = normalize_tools_hub_tab(
            st.session_state.get(TOOLS_HUB_TAB_KEY)
        )

    tabs = st.tabs(tab_labels)
    for tab, label in zip(tabs, tab_labels):
        with tab:
            if label == "Preprocessing":
                render_preprocess_panel(deps_ready=deps_ready)
            elif label == "Auto-merge":
                render_auto_merge_panel(deps_ready=deps_ready)
            elif label == "Manual merge":
                render_manual_merge_panel(deps_ready=deps_ready)
