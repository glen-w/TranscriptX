"""Analysis modules panel for transcript viewer."""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from transcriptx.web.module_option_format import format_module_option
from transcriptx.web.module_ui_groups import group_modules_for_ui, order_module_ids
from transcriptx.web.utils import get_analysis_modules


@dataclass(frozen=True)
class ModulePanelLayout:
    flat: list[str]
    groups: list[tuple[str, list[str]]]
    ungrouped: list[str]


def build_module_panel_layout(modules_raw: list[str]) -> ModulePanelLayout:
    modules_flat_ui = order_module_ids(modules_raw)
    groups_ui = group_modules_for_ui(modules_raw)
    spec_set = frozenset(mid for _, ids in groups_ui for mid in ids)
    modules_ungrouped = [m for m in modules_flat_ui if m not in spec_set]
    return ModulePanelLayout(
        flat=modules_flat_ui, groups=groups_ui, ungrouped=modules_ungrouped
    )


def render_modules_panel(selected_session: str) -> None:
    """Render modules selector and grouped action buttons."""
    st.session_state.setdefault("analysis_artifacts_version", 0)
    st.session_state.setdefault("analysis_run_in_progress", False)
    artifacts_version = st.session_state.get("analysis_artifacts_version", 0)
    modules_raw = get_analysis_modules(selected_session)
    layout = build_module_panel_layout(modules_raw)

    st.divider()
    st.subheader("📊 Analysis Modules")
    if not modules_raw:
        st.info(
            "No analysis modules run yet. Use **Run analysis** below to generate results."
        )
        st.info(
            "No analysis modules run yet. Use the Run Analysis page to analyze this transcript."
        )
        return

    select_key = f"analysis_module_select_{selected_session}_{artifacts_version}"
    current_module = st.session_state.get("analysis_module")
    default_index = (
        layout.flat.index(current_module)
        if current_module and current_module in layout.flat
        else 0
    )
    chosen = st.selectbox(
        "View analysis module",
        options=layout.flat,
        index=default_index,
        format_func=format_module_option,
        key=select_key,
    )
    if chosen:
        st.session_state["analysis_module"] = chosen
        st.session_state["analysis_session"] = selected_session

    first_expanded_done = False
    for title, ids in layout.groups:
        expanded = not first_expanded_done
        first_expanded_done = True
        with st.expander(title, expanded=expanded):
            cols = st.columns(min(len(ids), 4))
            for idx, module in enumerate(ids):
                with cols[idx % 4]:
                    if st.button(
                        module,
                        key=f"module_{module}_{title}",
                        width="stretch",
                    ):
                        st.session_state["analysis_module"] = module
                        st.session_state["analysis_session"] = selected_session
                        st.rerun()
    if layout.ungrouped:
        with st.expander("Other", expanded=not first_expanded_done):
            cols = st.columns(min(len(layout.ungrouped), 4))
            for idx, module in enumerate(layout.ungrouped):
                with cols[idx % 4]:
                    if st.button(
                        module,
                        key=f"module_other_{module}",
                        width="stretch",
                    ):
                        st.session_state["analysis_module"] = module
                        st.session_state["analysis_session"] = selected_session
                        st.rerun()
