"""Guided checkbox selector for Charts page Overview strip (`dashboard.overview_charts`)."""

from __future__ import annotations

from typing import Any, Sequence

import streamlit as st

from transcriptx.web import icons as ic
from transcriptx.core.utils.chart_registry import (
    get_chart_registry,
    get_default_overview_charts,
    iter_chart_definitions,
)
from transcriptx.web.components.info_tooltip import widget_help

OVERVIEW_CHARTS_KEY = "dashboard.overview_charts"
OVERVIEW_MAX_ITEMS_KEY = "dashboard.overview_max_items"
OVERVIEW_MISSING_KEY = "dashboard.overview_missing_behavior"


def normalize_overview_selection(raw: Any) -> list[str]:
    """Coerce draft/config value to an ordered list of viz_id strings."""
    if not raw:
        return []
    if isinstance(raw, str):
        return [raw] if raw.strip() else []
    if isinstance(raw, Sequence):
        out: list[str] = []
        for item in raw:
            text = str(item).strip()
            if text and text not in out:
                out.append(text)
        return out
    return []


def toggle_overview_chart(
    selected: list[str], viz_id: str, *, enabled: bool
) -> list[str]:
    """Add or remove viz_id while preserving order of remaining items."""
    current = normalize_overview_selection(selected)
    if enabled:
        if viz_id not in current:
            return [*current, viz_id]
        return current
    return [item for item in current if item != viz_id]


def move_overview_chart(selected: list[str], index: int, delta: int) -> list[str]:
    current = normalize_overview_selection(selected)
    if not current or index < 0 or index >= len(current):
        return current
    target = index + delta
    if target < 0 or target >= len(current):
        return current
    updated = list(current)
    updated[index], updated[target] = updated[target], updated[index]
    return updated


def charts_by_module() -> dict[str, list[tuple[str, str, str | None]]]:
    """module -> list of (viz_id, label, description)."""
    grouped: dict[str, list[tuple[str, str, str | None]]] = {}
    for chart in sorted(
        iter_chart_definitions(), key=lambda c: (c.module, c.rank_default, c.viz_id)
    ):
        desc = chart.description.strip() if chart.description else None
        grouped.setdefault(chart.module, []).append((chart.viz_id, chart.label, desc))
    return grouped


def _sync_overview_checkbox_keys(
    *,
    scope_key: str,
    selected: list[str],
) -> None:
    selected_set = set(selected)
    for viz_id in get_chart_registry():
        st.session_state[f"{scope_key}_ov_chk_{viz_id}"] = viz_id in selected_set


def render_charts_overview_selector(
    draft_dot: dict[str, Any],
    *,
    scope_key: str,
) -> dict[str, Any]:
    """Render selector and return updated flat-map keys for overview charts.

    Writes into ``draft_dot`` and returns the subset of keys this control owns.
    """
    st.markdown("**Charts overview**")
    st.caption(
        "Checked charts appear in the Charts page **Overview** section (in order below). "
        "The full gallery is unchanged. Empty selection = registry defaults for the run kind "
        "(transcript vs group)."
    )

    selected = normalize_overview_selection(draft_dot.get(OVERVIEW_CHARTS_KEY))
    registry = get_chart_registry()

    st.markdown("##### Selected (ordered)")
    if not selected:
        st.caption(
            "None selected — Charts Overview will use registry defaults for the run kind."
        )
    else:
        for idx, viz_id in enumerate(selected):
            chart = registry.get(viz_id)
            label = chart.label if chart else viz_id
            cols = st.columns([5, 1, 1, 1])
            with cols[0]:
                st.markdown(f"**{label}**")
                st.caption(f"`{viz_id}`")
            with cols[1]:
                if st.button(
                    "",
                    icon=ic.MOVE_UP,
                    key=f"{scope_key}_ov_up_{viz_id}",
                    disabled=idx == 0,
                ):
                    selected = move_overview_chart(selected, idx, -1)
                    draft_dot[OVERVIEW_CHARTS_KEY] = selected
                    _sync_overview_checkbox_keys(scope_key=scope_key, selected=selected)
                    st.rerun()
            with cols[2]:
                if st.button(
                    "",
                    icon=ic.MOVE_DOWN,
                    key=f"{scope_key}_ov_down_{viz_id}",
                    disabled=idx >= len(selected) - 1,
                ):
                    selected = move_overview_chart(selected, idx, 1)
                    draft_dot[OVERVIEW_CHARTS_KEY] = selected
                    _sync_overview_checkbox_keys(scope_key=scope_key, selected=selected)
                    st.rerun()
            with cols[3]:
                if st.button(
                    "", key=f"{scope_key}_ov_rm_{viz_id}", icon=ic.REMOVE
                ):
                    selected = toggle_overview_chart(selected, viz_id, enabled=False)
                    draft_dot[OVERVIEW_CHARTS_KEY] = selected
                    _sync_overview_checkbox_keys(scope_key=scope_key, selected=selected)
                    st.rerun()

    action_cols = st.columns(2)
    with action_cols[0]:
        if st.button(
            "Reset to transcript defaults",
            key=f"{scope_key}_ov_reset_defaults",
            icon=ic.RESET,
        ):
            selected = list(get_default_overview_charts())
            draft_dot[OVERVIEW_CHARTS_KEY] = selected
            _sync_overview_checkbox_keys(scope_key=scope_key, selected=selected)
            st.rerun()
    with action_cols[1]:
        if st.button(
            "Clear (use run-kind defaults)",
            key=f"{scope_key}_ov_clear",
            icon=ic.CLEAR,
        ):
            selected = []
            draft_dot[OVERVIEW_CHARTS_KEY] = selected
            _sync_overview_checkbox_keys(scope_key=scope_key, selected=selected)
            st.rerun()

    st.markdown("##### Available charts")
    selected_set = set(selected)
    for module, charts in charts_by_module().items():
        with st.expander(module, expanded=False):
            for viz_id, label, desc in charts:
                key = f"{scope_key}_ov_chk_{viz_id}"
                if key not in st.session_state:
                    st.session_state[key] = viz_id in selected_set
                checked = st.checkbox(
                    label,
                    key=key,
                    help=widget_help(desc or viz_id),
                )
                if checked != (viz_id in selected_set):
                    selected = toggle_overview_chart(selected, viz_id, enabled=checked)
                    draft_dot[OVERVIEW_CHARTS_KEY] = selected
                    _sync_overview_checkbox_keys(scope_key=scope_key, selected=selected)
                    st.rerun()

    max_items = draft_dot.get(OVERVIEW_MAX_ITEMS_KEY)
    missing = draft_dot.get(OVERVIEW_MISSING_KEY, "skip")
    with st.expander("Overview display options", expanded=False):
        new_max = st.number_input(
            "Max overview items (optional)",
            min_value=0,
            value=int(max_items) if isinstance(max_items, int) and max_items > 0 else 0,
            step=1,
            key=f"{scope_key}_ov_max_items",
            help=widget_help("0 means no limit."),
        )
        draft_dot[OVERVIEW_MAX_ITEMS_KEY] = int(new_max) if int(new_max) > 0 else None
        draft_dot[OVERVIEW_MISSING_KEY] = st.selectbox(
            "When a selected chart is missing",
            options=["skip", "show_placeholder"],
            index=0 if missing != "show_placeholder" else 1,
            key=f"{scope_key}_ov_missing",
            help=widget_help(
                "skip hides missing charts; show_placeholder reserves a slot with a notice."
            ),
        )

    return {
        OVERVIEW_CHARTS_KEY: draft_dot.get(OVERVIEW_CHARTS_KEY, []),
        OVERVIEW_MAX_ITEMS_KEY: draft_dot.get(OVERVIEW_MAX_ITEMS_KEY),
        OVERVIEW_MISSING_KEY: draft_dot.get(OVERVIEW_MISSING_KEY, "skip"),
    }
