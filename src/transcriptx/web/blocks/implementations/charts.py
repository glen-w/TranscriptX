"""Charts page block implementations (gallery sections extracted for reuse)."""

from __future__ import annotations

from typing import Dict, List

import streamlit as st

from transcriptx.web.blocks.context import BlockContext
from transcriptx.web.blocks.placement import BlockPlacement
from transcriptx.web.models.artifact import Artifact
from transcriptx.web.module_ui_groups import order_strings_like_modules
from transcriptx.web.state import (
    CHARTS_KEY_EXPAND_ALL,
    CHARTS_KEY_FILTER_MODULE,
    CHARTS_KEY_FILTER_SCOPE,
    CHARTS_KEY_FILTER_SLICE_ID,
    CHARTS_KEY_FILTER_SUBVIEW,
    CHARTS_KEY_FILTER_TAGS,
    CHARTS_KEY_SHOW_SUMMARY_TOGGLE,
    CHARTS_KEY_SOURCE_PRESET,
    CHARTS_KEY_DYNAMIC_TOGGLE,
    CHARTS_KEY_STATIC_TOGGLE,
)


def _chart_artifacts(ctx: BlockContext) -> List[Artifact]:
    return [a for a in ctx.artifacts if a.kind in {"chart_static", "chart_dynamic"}]


def _kind_filter_from_session() -> str | None:
    show_static = st.session_state.get(CHARTS_KEY_STATIC_TOGGLE, True)
    show_dynamic = st.session_state.get(CHARTS_KEY_DYNAMIC_TOGGLE, True)
    if show_static and show_dynamic:
        return None
    if show_static and not show_dynamic:
        return "chart_static"
    if not show_static and show_dynamic:
        return "chart_dynamic"
    return "__none__"


def render_chart_gallery_modules(
    run_root,
    charts: List[Artifact],
    *,
    sections_expanded: bool,
    render_family_section,
) -> None:
    """Render per-module chart expanders (gallery portion of Charts page)."""
    module_groups: Dict[str, List[Artifact]] = {}
    for chart in charts:
        module = chart.module or "Other"
        module_groups.setdefault(module, []).append(chart)

    for module_name in order_strings_like_modules(list(module_groups.keys())):
        module_charts = module_groups[module_name]
        with st.expander(
            f"📊 {module_name} ({len(module_charts)} chart"
            f"{'s' if len(module_charts) != 1 else ''})",
            expanded=sections_expanded,
        ):
            from transcriptx.web.services.chart_view_model_service import (
                group_charts_into_families,
            )

            families = group_charts_into_families(module_charts)
            for fi, family in enumerate(families):
                render_family_section(
                    run_root,
                    family,
                    f"chart_{module_name}_{family.key}",
                    sections_expanded=sections_expanded,
                    show_family_expander=True,
                )
                if fi < len(families) - 1:
                    st.divider()


def render_chart_gallery(ctx: BlockContext, _placement: BlockPlacement) -> None:
    """Compose the Charts gallery from run artifacts + session filter state."""
    if ctx.run_root is None:
        st.info("Select a run to browse chart artifacts.")
        return
    charts = _chart_artifacts(ctx)
    if not charts:
        st.caption("No chart artifacts for this run.")
        return

    from transcriptx.web.services.chart_view_model_service import apply_chart_filters

    filtered = apply_chart_filters(
        charts,
        module=st.session_state.get(CHARTS_KEY_FILTER_MODULE),
        scope=st.session_state.get(CHARTS_KEY_FILTER_SCOPE),
        kind=_kind_filter_from_session(),
        tags=st.session_state.get(CHARTS_KEY_FILTER_TAGS) or None,
        subview=st.session_state.get(CHARTS_KEY_FILTER_SUBVIEW),
        slice_id=st.session_state.get(CHARTS_KEY_FILTER_SLICE_ID),
    )
    if not filtered:
        st.caption("No charts match the current filters.")
        return

    from transcriptx.web.page_modules.charts import _render_chart_family_section

    sections_expanded = bool(st.session_state.get(CHARTS_KEY_EXPAND_ALL, False))
    render_chart_gallery_modules(
        ctx.run_root,
        filtered,
        sections_expanded=sections_expanded,
        render_family_section=_render_chart_family_section,
    )


def render_chart_overview_slots(ctx: BlockContext, _placement: BlockPlacement) -> None:
    """Compose Charts overview slots from run artifacts + session config."""
    if ctx.run_root is None:
        st.info("Select a run to view overview chart slots.")
        return
    all_charts = _chart_artifacts(ctx)
    if not all_charts:
        st.caption("No chart artifacts for this run.")
        return

    from transcriptx.web.page_modules.charts import (
        _overview_candidate_charts,
        _render_chart_family_section,
    )
    from transcriptx.web.services.chart_view_model_service import (
        build_overview_slots,
        family_from_overview_slot,
    )
    from transcriptx.web.services.config_resolution_service import (
        resolve_effective_config,
    )

    chart_source = st.session_state.get(CHARTS_KEY_SOURCE_PRESET) or "All"
    # Charts page uses "All" / "Group aggregate" / "Member sessions"
    if chart_source == "All charts":
        chart_source = "All"
    tag_filter = list(st.session_state.get(CHARTS_KEY_FILTER_TAGS) or [])
    overview_candidates = _overview_candidate_charts(
        all_charts, chart_source, tag_filter
    )

    resolved = (
        resolve_effective_config(run_dir=ctx.run_root)
        if ctx.run_root.exists()
        else resolve_effective_config(run_dir=None)
    )
    dashboard_config = (
        getattr(resolved.effective_config, "dashboard", None) if resolved else None
    )
    user_overview = getattr(dashboard_config, "overview_charts", None) or []
    max_items = getattr(dashboard_config, "overview_max_items", None)
    missing_behavior = getattr(dashboard_config, "overview_missing_behavior", "skip")

    overview_slots = build_overview_slots(
        overview_candidates=overview_candidates,
        user_overview=user_overview,
        missing_behavior=missing_behavior,
        max_items=max_items,
    )
    if not overview_slots:
        st.caption("No overview slots configured for this run.")
        return

    if not st.session_state.get(CHARTS_KEY_SHOW_SUMMARY_TOGGLE, True):
        st.caption("Overview slots are hidden (Show Overview is off).")
        return

    sections_expanded = bool(st.session_state.get(CHARTS_KEY_EXPAND_ALL, False))
    for slot in overview_slots:
        st.markdown(f"**{slot['label']}**")
        slot_description = slot.get("description")
        if slot_description:
            st.caption(slot_description)
        if slot.get("missing"):
            st.caption("Chart not available for this run.")
            st.divider()
            continue
        family = family_from_overview_slot(slot)
        if family:
            _render_chart_family_section(
                ctx.run_root,
                family,
                f"block_overview_chart_{slot['viz_id']}",
                sections_expanded=sections_expanded,
                show_family_expander=False,
            )
        st.divider()
