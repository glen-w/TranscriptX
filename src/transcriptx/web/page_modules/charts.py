"""
Charts gallery page for TranscriptX Studio.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Dict

import streamlit as st
from PIL import Image

from transcriptx.core.config import (
    resolve_effective_config,
    get_default_config_dict,
)
from transcriptx.core.utils.chart_registry import (
    get_chart_definition,
    get_chart_registry,
    get_default_overview_charts,
    select_preferred_artifacts,
)
from transcriptx.web.models.artifact import Artifact, ArtifactFilters
from transcriptx.web.services import ArtifactService, FileService
from transcriptx.web.services.artifact_service import (
    MAX_INLINE_HTML_BYTES,
    MAX_FULLSCREEN_HTML_BYTES,
)


def _get_filter_state(key: str, default):
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]


def _resolve_overview_artifacts(
    viz_id: str, artifacts: list[Artifact]
) -> list[Artifact]:
    chart_def = get_chart_definition(viz_id)
    if not chart_def:
        return []
    matches = [a for a in artifacts if chart_def.match.matches(a, chart_def)]
    return select_preferred_artifacts(matches, chart_def)


def render_charts() -> None:
    session = st.session_state.get("selected_session")
    run_id = st.session_state.get("selected_run_id")
    if not session or not run_id:
        st.info("Select a session and run to view charts.")
        return

    st.subheader("Charts Gallery")

    # Get ALL charts first (without filters) for the overview section
    all_artifacts = ArtifactService.list_artifacts(session, run_id)
    all_charts = [a for a in all_artifacts if a.kind in {"chart_static", "chart_dynamic"}]

    if not all_charts:
        st.warning("No chart artifacts found.")
        return

    # Get filter state
    module_filter = _get_filter_state("filter_module", None)
    scope_filter = _get_filter_state("filter_scope", None)
    show_static = _get_filter_state("filter_show_static", True)
    show_dynamic = _get_filter_state("filter_show_dynamic", True)
    tag_filter = _get_filter_state("filter_tags", [])

    # Get available filter options from all charts
    modules = sorted({a.module for a in all_charts if a.module})
    scopes = sorted({a.scope for a in all_charts if a.scope})
    tags = sorted({tag for a in all_charts for tag in a.tags})

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.session_state["filter_module"] = st.selectbox(
            "Module", [None] + modules, index=0
        )
    with col2:
        st.session_state["filter_scope"] = st.selectbox(
            "Scope", [None] + scopes, index=0
        )
    with col3:
        st.markdown("**Type**")
        col3a, col3b = st.columns(2)
        with col3a:
            st.session_state["filter_show_static"] = st.toggle(
                "Static",
                value=show_static,
                key="filter_static_toggle"
            )
        with col3b:
            st.session_state["filter_show_dynamic"] = st.toggle(
                "Dynamic",
                value=show_dynamic,
                key="filter_dynamic_toggle"
            )
    with col4:
        st.session_state["filter_tags"] = st.multiselect(
            "Tags", tags, default=tag_filter
        )

    # Toggle controls under filter selection
    toggle_col1, toggle_col2 = st.columns(2)
    with toggle_col1:
        # Default to True (collapsed state) - page starts with all collapsed except summary
        collapse_all = _get_filter_state("collapse_all", True)
        st.session_state["collapse_all"] = st.toggle(
            "Collapse/Expand All",
            value=collapse_all,
            key="collapse_all_toggle"
        )
    with toggle_col2:
        show_summary = _get_filter_state("show_summary_charts", True)
        st.session_state["show_summary_charts"] = st.toggle(
            "Show Summary Charts",
            value=show_summary,
            key="show_summary_toggle"
        )

    # Determine kind filter based on toggle states
    # If both are on, show all (None)
    # If only one is on, filter to that type
    # If both are off, show none (empty list)
    show_static = st.session_state.get("filter_show_static", True)
    show_dynamic = st.session_state.get("filter_show_dynamic", True)
    if show_static and show_dynamic:
        kind_filter = None  # Show all types
    elif show_static and not show_dynamic:
        kind_filter = "chart_static"
    elif not show_static and show_dynamic:
        kind_filter = "chart_dynamic"
    else:
        # Both off - show no charts in gallery (overview section still shows)
        kind_filter = "__none__"  # Special value that won't match any charts

    # Apply filters for the gallery section
    if kind_filter == "__none__":
        charts = []  # Show no charts when both toggles are off
    else:
        charts = [
            a
            for a in all_charts
            if ArtifactFilters(
                module=st.session_state["filter_module"],
                scope=st.session_state["filter_scope"],
                kind=kind_filter,
                tags=st.session_state["filter_tags"] or None,
            ).matches(a)
        ]

    full_screen_id = st.session_state.get("full_screen_artifact")
    if full_screen_id:
        # Check both filtered charts and all charts for full screen view
        selected = next((a for a in all_charts if a.id == full_screen_id), None)
        if selected:
            st.subheader(selected.title or selected.rel_path)
            if st.button("Close Full Screen"):
                st.session_state["full_screen_artifact"] = None
                st.rerun()
            if selected.kind == "chart_static":
                path = ArtifactService._resolve_safe_path(
                    ArtifactService._resolve_run_dir(session, run_id),
                    selected.rel_path,
                )
                if path and path.exists():
                    st.image(Image.open(path), width='stretch')
            else:
                html_payload = ArtifactService.load_html_artifact(session, run_id, selected)
                if not html_payload:
                    st.error("Unable to load HTML chart.")
                else:
                    size = html_payload["bytes"]
                    if size > MAX_FULLSCREEN_HTML_BYTES:
                        st.warning("HTML chart is too large to render. Download instead.")
                    else:
                        st.components.v1.html(
                            html_payload["content"],
                            height=700,
                            scrolling=True,
                        )
        st.divider()

    # Identify overview charts using ALL charts (not filtered)
    # Use effective config resolution to load from project config file
    # This ensures we get config from .transcriptx/config.json if it exists
    run_dir = FileService._resolve_session_dir(f"{session}/{run_id}")
    resolved = resolve_effective_config(run_dir=run_dir) if run_dir and run_dir.exists() else resolve_effective_config(run_dir=None)
    if resolved:
        config = resolved.effective_config
        dashboard_config = getattr(config, "dashboard", None)
    else:
        # Fallback to defaults if config resolution fails
        dashboard_config = None
    
    registry = get_chart_registry()
    enabled_viz_ids = getattr(dashboard_config, "overview_charts", []) or []
    # Fall back to defaults if no overview charts are configured
    if not enabled_viz_ids:
        enabled_viz_ids = get_default_overview_charts()
    max_items = getattr(dashboard_config, "overview_max_items", None)
    if isinstance(max_items, int) and max_items > 0:
        enabled_viz_ids = enabled_viz_ids[:max_items]

    overview_slots: list[dict] = []
    missing_behavior = getattr(
        dashboard_config, "overview_missing_behavior", "skip"
    )
    for viz_id in enabled_viz_ids:
        chart_def = registry.get(viz_id)
        if not chart_def:
            if missing_behavior == "show_placeholder":
                overview_slots.append(
                    {
                        "label": f"{viz_id} (not available)",
                        "viz_id": viz_id,
                        "artifacts": [],
                        "missing": True,
                    }
                )
            continue
        # Use all_charts instead of filtered charts for overview
        matching = _resolve_overview_artifacts(viz_id, all_charts)
        if matching or missing_behavior == "show_placeholder":
            display_title = (
                matching[0].title if matching and matching[0].title else chart_def.label
            )
            overview_slots.append(
                {
                    "label": display_title,
                    "viz_id": viz_id,
                    "artifacts": matching,
                    "cardinality": chart_def.cardinality,
                    "missing": not matching,
                }
            )

    overview_chart_count = sum(
        len(slot["artifacts"]) for slot in overview_slots if slot["artifacts"]
    )
    overview_slot_count = len(overview_slots)
    display_overview_count = overview_chart_count or overview_slot_count

    # Display Overview section at the top (collapsible)
    # Overview section always stays expanded (summary charts are always visible)
    if overview_slot_count and st.session_state.get("show_summary_charts", True):
        overview_expanded = True  # Always expanded, regardless of toggle
        with st.expander(
            f"📋 Overview ({display_overview_count} chart{'s' if display_overview_count != 1 else ''})",
            expanded=overview_expanded,
        ):
            for slot in overview_slots:
                st.markdown(f"**{slot['label']}**")
                if slot.get("missing"):
                    st.info("Chart not available for this run.")
                    st.divider()
                    continue
                slot_charts = slot.get("artifacts", [])
                cols = st.columns(3)
                for idx, chart in enumerate(slot_charts):
                    with cols[idx % 3]:
                        st.caption(chart.title or chart.rel_path)
                        if chart.kind == "chart_static":
                            thumb_path = ArtifactService.generate_thumbnail(
                                session, run_id, chart
                            )
                            if thumb_path and Path(thumb_path).exists():
                                st.image(Image.open(thumb_path), width='stretch')
                            else:
                                st.write("Thumbnail unavailable")
                        else:
                            st.info("Dynamic chart (HTML)")
                            html_payload = ArtifactService.load_html_artifact(
                                session, run_id, chart
                            )
                            if html_payload:
                                size = html_payload["bytes"]
                                if size <= MAX_INLINE_HTML_BYTES:
                                    st.components.v1.html(
                                        html_payload["content"],
                                        height=400,
                                        scrolling=True,
                                    )
                                elif size <= MAX_FULLSCREEN_HTML_BYTES:
                                    st.caption("Open for full-screen view.")
                                else:
                                    st.caption("Too large to render inline.")
                        if st.button("View", key=f"overview_chart_{slot['viz_id']}_{chart.id}"):
                            st.session_state["full_screen_artifact"] = chart.id
                            st.rerun()
                st.divider()

    # Group all charts by module (including overview charts)
    module_groups = {}
    for chart in charts:
        module = chart.module or "Other"
        if module not in module_groups:
            module_groups[module] = []
        module_groups[module].append(chart)

    # Display charts grouped by module in collapsible sections
    # Module groups should be collapsed when collapse_all is True (default)
    # and expanded when collapse_all is False
    module_expanded = not st.session_state.get("collapse_all", True)
    for module_name in sorted(module_groups.keys()):
        module_charts = module_groups[module_name]
        with st.expander(
            f"📊 {module_name} ({len(module_charts)} chart{'s' if len(module_charts) != 1 else ''})",
            expanded=module_expanded,
        ):
            cols = st.columns(3)
            for idx, chart in enumerate(module_charts):
                with cols[idx % 3]:
                    st.caption(chart.title or chart.rel_path)
                    if chart.kind == "chart_static":
                        thumb_path = ArtifactService.generate_thumbnail(session, run_id, chart)
                        if thumb_path and Path(thumb_path).exists():
                            st.image(Image.open(thumb_path), width='stretch')
                        else:
                            st.write("Thumbnail unavailable")
                    else:
                        st.info("Dynamic chart (HTML)")
                        html_payload = ArtifactService.load_html_artifact(session, run_id, chart)
                        if html_payload:
                            size = html_payload["bytes"]
                            if size <= MAX_INLINE_HTML_BYTES:
                                st.components.v1.html(
                                    html_payload["content"],
                                    height=400,
                                    scrolling=True,
                                )
                            elif size <= MAX_FULLSCREEN_HTML_BYTES:
                                st.caption("Open for full-screen view.")
                            else:
                                st.caption("Too large to render inline.")
                    if st.button("View", key=f"chart_{chart.id}"):
                        st.session_state["full_screen_artifact"] = chart.id
                        st.rerun()
