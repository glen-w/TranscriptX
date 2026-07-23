"""Charts page block implementations (gallery sections extracted for reuse)."""

from __future__ import annotations

from typing import List

import streamlit as st

from transcriptx.web.blocks.context import BlockContext
from transcriptx.web.blocks.placement import BlockPlacement
from transcriptx.web.charts_filter_state import (
    chart_text_flags,
    ensure_charts_chart_text,
    kind_filter_from_session,
    scope_filter_from_session,
)
from transcriptx.web.models.artifact import Artifact
from transcriptx.web.state import (
    CHARTS_KEY_FILTER_MODULE,
    CHARTS_KEY_FILTER_SLICE_ID,
    CHARTS_KEY_FILTER_SUBVIEW,
    CHARTS_KEY_FILTER_TAGS,
    CHARTS_KEY_MODULE_SORT,
    CHARTS_KEY_SEARCH,
    CHARTS_KEY_SOURCE_PRESET,
    CHARTS_SORT_MODULE_FAMILY,
)


def _chart_artifacts(ctx: BlockContext) -> List[Artifact]:
    return [a for a in ctx.artifacts if a.kind in {"chart_static", "chart_dynamic"}]


def render_chart_gallery_modules(
    run_root,
    charts: List[Artifact],
    *,
    sections_expanded: bool,
    render_family_section,
) -> None:
    """Render per-module chart sections (gallery portion of Charts page)."""
    from transcriptx.web.services.chart_view_model_service import (
        group_charts_into_families,
        module_group_counts,
        sort_gallery_module_ids,
    )

    groups = module_group_counts(charts)
    sort_mode = st.session_state.get(CHARTS_KEY_MODULE_SORT, CHARTS_SORT_MODULE_FAMILY)
    ordered = sort_gallery_module_ids(groups.keys(), sort_mode=str(sort_mode))
    show_registry, show_llm = chart_text_flags(ensure_charts_chart_text(st.session_state))

    for module_id in ordered:
        group = groups[module_id]
        label = (
            f"{group.display_name} · {group.total} chart"
            f"{'s' if group.total != 1 else ''}"
        )
        with st.expander(label, expanded=sections_expanded):
            families = group_charts_into_families(group.charts)
            for fi, family in enumerate(families):
                render_family_section(
                    run_root,
                    family,
                    f"chart_{module_id}_{family.key}",
                    sections_expanded=sections_expanded,
                    show_family_expander=True,
                    show_registry_description=show_registry,
                    show_llm_summary=show_llm,
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
        scope=scope_filter_from_session(st.session_state),
        kind=kind_filter_from_session(st.session_state),
        tags=st.session_state.get(CHARTS_KEY_FILTER_TAGS) or None,
        subview=st.session_state.get(CHARTS_KEY_FILTER_SUBVIEW),
        slice_id=st.session_state.get(CHARTS_KEY_FILTER_SLICE_ID),
        search=st.session_state.get(CHARTS_KEY_SEARCH) or "",
    )
    if not filtered:
        st.caption("No charts match the current filters.")
        return

    from transcriptx.web.page_modules.charts import _render_chart_family_section

    render_chart_gallery_modules(
        ctx.run_root,
        filtered,
        sections_expanded=False,
        render_family_section=_render_chart_family_section,
    )


def render_chart_overview_slots(ctx: BlockContext, _placement: BlockPlacement) -> None:
    """Compose Charts overview slots from the canonical filtered chart collection."""
    if ctx.run_root is None:
        st.info("Select a run to view overview chart slots.")
        return
    all_charts = _chart_artifacts(ctx)
    if not all_charts:
        st.caption("No chart artifacts for this run.")
        return

    from transcriptx.core.config import resolve_effective_config
    from transcriptx.web.page_modules.charts import _render_chart_family_section
    from transcriptx.web.services.chart_view_model_service import (
        build_charts_gallery_view,
        family_from_overview_slot,
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

    view = build_charts_gallery_view(
        all_charts,
        module=st.session_state.get(CHARTS_KEY_FILTER_MODULE),
        scope=scope_filter_from_session(st.session_state),
        kind=kind_filter_from_session(st.session_state),
        tags=st.session_state.get(CHARTS_KEY_FILTER_TAGS) or None,
        subview=st.session_state.get(CHARTS_KEY_FILTER_SUBVIEW),
        slice_id=st.session_state.get(CHARTS_KEY_FILTER_SLICE_ID),
        search=st.session_state.get(CHARTS_KEY_SEARCH) or "",
        sort_mode=str(
            st.session_state.get(CHARTS_KEY_MODULE_SORT, CHARTS_SORT_MODULE_FAMILY)
        ),
        user_overview=user_overview,
        missing_behavior=missing_behavior,
        max_items=max_items,
    )
    if not view.overview_slots:
        st.caption("No overview slots for the current filters.")
        return

    show_registry, show_llm = chart_text_flags(ensure_charts_chart_text(st.session_state))
    for slot in view.overview_slots:
        st.markdown(f"**{slot['label']}**")
        slot_description = slot.get("description")
        if slot_description and show_registry:
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
                sections_expanded=False,
                show_family_expander=False,
                show_registry_description=show_registry,
                show_llm_summary=show_llm,
            )
        st.divider()
