"""
Charts gallery page for TranscriptX Studio.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import streamlit as st
from PIL import Image

from transcriptx.web.charts_filter_state import reset_charts_filters_to_defaults
from transcriptx.core.config import (
    resolve_effective_config,
)
from transcriptx.web.blocks.filters.subview_slice import render_subview_slice_filter
from transcriptx.web.components.empty_state import render_empty_state
from transcriptx.web.components.page_shell import render_page_help, render_page_shell
from transcriptx.web.components.run_scoped_page import (
    RunScopedPageConfig,
    RunScopedPageContext,
    render_run_scoped_page,
)
from transcriptx.web.models.artifact import Artifact
from transcriptx.web.services import ArtifactService
from transcriptx.web.services.chart_view_model_service import (
    ChartGalleryFamily,
    apply_chart_filters,
    build_filter_options,
    build_overview_slots,
    compute_chart_badges,
    family_from_overview_slot,
    group_charts_into_families,
    resolve_chart_description,
)
from transcriptx.web.services.artifact_service import (
    MAX_INLINE_HTML_BYTES,
    MAX_FULLSCREEN_HTML_BYTES,
)
from transcriptx.utils.charts_export import ChartsExportResult
from transcriptx.web.services.export_service import ExportService
from transcriptx.web.module_option_format import format_module_option
from transcriptx.web.module_ui_groups import order_strings_like_modules
from transcriptx.web.state import (
    CHARTS_KEY_EXPORT_RESULT,
    CHARTS_KEY_EXPORT_SIG,
    CHARTS_KEY_EXPAND_ALL,
    CHARTS_KEY_FILTERS_INIT,
    CHARTS_KEY_FILTER_MODULE,
    CHARTS_KEY_FILTER_SCOPE,
    CHARTS_KEY_FILTER_SLICE_ID,
    CHARTS_KEY_FILTER_SUBVIEW,
    CHARTS_KEY_FILTER_TAGS,
    CHARTS_KEY_FULL_SCREEN,
    CHARTS_KEY_SHOW_SUMMARY_TOGGLE,
    CHARTS_KEY_SLICE_SELECTOR,
    CHARTS_KEY_SOURCE_PRESET,
    CHARTS_KEY_STATIC_TOGGLE,
    CHARTS_KEY_DYNAMIC_TOGGLE,
    CHARTS_KEY_SUBVIEW_TABS,
    CHARTS_KEY_TAGS_MULTI,
    SELECTBOX_PLACEHOLDER_MODULE,
)

_CHARTS_HELP_PREREQ = (
    "**What this shows:** Chart artifacts for the selected run.\n\n"
    "**If empty:** Select a subject and run in the sidebar."
)
_CHARTS_HELP_LOADED = (
    "**What this shows:** All chart artifacts produced by analysis modules for the "
    "selected run.\n\n**If empty:** Run analysis for this transcript or group, or pick "
    "another run. **Filters:** Narrow by module, scope, tags, or chart type; **Reset filters** "
    "restores defaults for this page.\n\n**Reading charts:** Each chart shows a short "
    "interpretation caption under its title when one is available."
)

_CHARTS_CONFIG = RunScopedPageConfig(
    title="Charts Gallery",
    description="Browse static and dynamic chart artifacts for the current run.",
    prereq_help_md=_CHARTS_HELP_PREREQ,
    empty_headline="No subject or run selected",
    empty_detail="Pick a transcript or group and a run in the sidebar to view charts.",
    primary_action=("Open Library", "Library"),
    secondary_action=("Run Analysis", "Run Analysis"),
    loaded_help_md=_CHARTS_HELP_LOADED,
)


def _group_aggregate_semantics_caption(chart: Artifact) -> str:
    """
    Short caption aligned with real group chart semantics (not a generic
    "aggregated across sessions" for temporal overlays, pooled views, etc.).
    """
    if chart.has_tag("group_visual_special_path"):
        return "Group word cloud via wordclouds module path (not GROUP_CHART_REGISTRY)"
    meta = chart.meta or {}
    vid = meta.get("viz_id")
    if not isinstance(vid, str):
        vid = ""
    rp = (chart.rel_path or "").lower()
    if not vid and "wordcloud" in rp:
        return "Group word cloud via wordclouds module path (not GROUP_CHART_REGISTRY)"
    if ".temporal_overlay." in vid:
        return (
            "Multi-session overlay (session-relative time — not a single wall-clock "
            "timeline)"
        )
    if "cross_session_speaker" in vid:
        return "Same canonical speaker compared across sessions in this group"
    if ".pooled." in vid:
        return (
            "Pooled single view (corpus-level merge; see module / docs for semantics)"
        )
    if ".session." in vid:
        return "One value per transcript in this group"
    if "global_acts_pie" in vid:
        return "Corpus-level dialogue-act mix for this group (audited pooled view)"
    if vid.startswith("group."):
        return "Group run summary chart"
    return "Group run chart"


def _overview_candidate_charts(
    all_charts: list[Artifact], chart_source: str, tag_filter: list[str]
) -> list[Artifact]:
    """Charts pool for overview: same tag semantics as gallery preset + optional tags."""
    if chart_source == "Group aggregate":
        return [a for a in all_charts if "group_aggregate" in a.tags]
    if chart_source == "Member sessions":
        return [a for a in all_charts if "member_session" in a.tags]
    if tag_filter:
        return [a for a in all_charts if all(t in a.tags for t in tag_filter)]
    return list(all_charts)


def _render_chart_gallery_card(
    run_root: Path,
    chart: Artifact,
    button_key: str,
) -> None:
    """Single chart thumbnail / preview with full-screen action."""
    tags_s = ", ".join(sorted(chart.tags)) if chart.tags else "—"
    meta = f"{chart.module or '—'} · {chart.scope or '—'} · {chart.kind} · {tags_s}"
    with st.container(border=True):
        st.markdown(
            f'<div class="tx-chart-card-meta">{meta}</div>',
            unsafe_allow_html=True,
        )
        st.caption(chart.title or chart.rel_path)
        description = resolve_chart_description(chart)
        if description:
            st.caption(description)
        elif chart.has_tag("group_aggregate"):
            st.caption(_group_aggregate_semantics_caption(chart))
        if chart.kind == "chart_static":
            thumb_path = ArtifactService.generate_thumbnail(run_root, chart)
            if thumb_path and Path(thumb_path).exists():
                st.image(Image.open(thumb_path), width="stretch")
            else:
                st.caption("Thumbnail unavailable")
        else:
            st.caption("Dynamic chart (HTML)")
            html_payload = ArtifactService.load_html_artifact(run_root, chart)
            if html_payload:
                size = html_payload["bytes"]
                if size <= MAX_INLINE_HTML_BYTES:
                    st.iframe(html_payload["content"], height=400)
                elif size <= MAX_FULLSCREEN_HTML_BYTES:
                    st.caption("Too large for inline preview — open full screen.")
                else:
                    st.caption(
                        "Too large to render — use full screen or open artifact on disk."
                    )
            if st.button(
                "⛶",
                key=button_key,
                help="Open full screen",
                type="secondary",
            ):
                st.session_state[CHARTS_KEY_FULL_SCREEN] = chart.id
                st.rerun()


def _render_chart_card_grid(
    run_root: Path,
    artifacts: list[Artifact],
    key_prefix: str,
) -> None:
    cols = st.columns(3)
    for idx, chart in enumerate(artifacts):
        with cols[idx % 3]:
            _render_chart_gallery_card(
                run_root, chart, f"{key_prefix}_{chart.id}_{idx}"
            )


def _family_renders_directly(family: ChartGalleryFamily) -> bool:
    return family.cardinality in {"single", "paired_static_dynamic"} or (
        len(family.slices) == 1 and family.slices[0].key == "all"
    )


def _render_chart_family_slices(
    run_root: Path,
    family: ChartGalleryFamily,
    key_prefix: str,
    *,
    sections_expanded: bool,
) -> None:
    if _family_renders_directly(family):
        artifacts = family.slices[0].artifacts if family.slices else []
        _render_chart_card_grid(run_root, artifacts, key_prefix)
        return

    for sl in family.slices:
        if not sl.label:
            _render_chart_card_grid(run_root, sl.artifacts, f"{key_prefix}_{sl.key}")
            continue
        with st.expander(
            f"{sl.label} ({len(sl.artifacts)})",
            expanded=sections_expanded,
        ):
            st.markdown('<div class="tx-chart-slice-shell">', unsafe_allow_html=True)
            _render_chart_card_grid(run_root, sl.artifacts, f"{key_prefix}_{sl.key}")
            st.markdown("</div>", unsafe_allow_html=True)


def _render_chart_family_section(
    run_root: Path,
    family: ChartGalleryFamily,
    key_prefix: str,
    *,
    sections_expanded: bool,
    show_family_expander: bool = True,
) -> None:
    if show_family_expander:
        with st.expander(
            f"{family.label} ({family.artifact_count})",
            expanded=sections_expanded,
        ):
            if family.description:
                st.caption(family.description)
            st.markdown('<div class="tx-chart-family-shell">', unsafe_allow_html=True)
            _render_chart_family_slices(
                run_root,
                family,
                key_prefix,
                sections_expanded=sections_expanded,
            )
            st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown('<div class="tx-chart-family-shell">', unsafe_allow_html=True)
        _render_chart_family_slices(
            run_root,
            family,
            key_prefix,
            sections_expanded=sections_expanded,
        )
        st.markdown("</div>", unsafe_allow_html=True)


def _ensure_charts_filters_for_run(subject_id: str, run_id: str) -> None:
    marker = st.session_state.get(CHARTS_KEY_FILTERS_INIT)
    identity = f"{subject_id}|{run_id}"
    if marker != identity:
        reset_charts_filters_to_defaults(st.session_state)
        st.session_state[CHARTS_KEY_FILTERS_INIT] = identity
        st.session_state.pop(CHARTS_KEY_EXPORT_RESULT, None)
        st.session_state.pop(CHARTS_KEY_EXPORT_SIG, None)


def _charts_export_signature(charts: list[Artifact]) -> frozenset[str]:
    return frozenset(a.id for a in charts)


def _has_current_export(
    stored_result: object, stored_sig: object, current_sig: frozenset[str]
) -> bool:
    return isinstance(stored_result, ChartsExportResult) and stored_sig == current_sig


@st.fragment
def _charts_filters_and_gallery_fragment(
    run_root: Path,
    all_charts: list[Artifact],
    modules: list[str],
    scopes: list[str],
    tags: list[str],
    subviews: list[str],
    user_overview: Sequence[Any],
    max_items: Optional[int],
    missing_behavior: str,
) -> None:
    col_reset, _ = st.columns([1, 4])
    with col_reset:
        if st.button("Reset filters", key="charts_reset_filters"):
            reset_charts_filters_to_defaults(st.session_state)
            try:
                st.rerun(scope="fragment")
            except TypeError:
                st.rerun()

    st.caption(
        "Member session charts are merged from each transcript run in the group; "
        "group aggregate charts summarize the whole group."
    )
    st.radio(
        "Show charts from",
        options=["All", "Group aggregate", "Member sessions"],
        horizontal=True,
        key=CHARTS_KEY_SOURCE_PRESET,
        help="Quick filter by how charts were produced (uses artifact tags).",
    )
    chart_source = st.session_state.get(CHARTS_KEY_SOURCE_PRESET, "All")
    if chart_source == "Group aggregate":
        st.session_state[CHARTS_KEY_FILTER_TAGS] = ["group_aggregate"]
    elif chart_source == "Member sessions":
        st.session_state[CHARTS_KEY_FILTER_TAGS] = ["member_session"]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.selectbox(
            "Module",
            [None] + modules,
            format_func=lambda m: (
                SELECTBOX_PLACEHOLDER_MODULE if m is None else format_module_option(m)
            ),
            key=CHARTS_KEY_FILTER_MODULE,
        )
    with col2:
        st.selectbox(
            "Scope",
            [None] + scopes,
            key=CHARTS_KEY_FILTER_SCOPE,
        )
    with col3:
        st.markdown("**Type**")
        col3a, col3b = st.columns(2)
        with col3a:
            st.toggle("Static", key=CHARTS_KEY_STATIC_TOGGLE)
        with col3b:
            st.toggle("Dynamic", key=CHARTS_KEY_DYNAMIC_TOGGLE)
    with col4:
        if chart_source == "All":
            st.multiselect("Tags", tags, key=CHARTS_KEY_TAGS_MULTI)
        else:
            locked_defaults = st.session_state.get(CHARTS_KEY_FILTER_TAGS) or []
            # Preset filters use tags that may not appear on any artifact in this run;
            # multiselect defaults must be subsets of options.
            tag_options = sorted(set(tags) | set(locked_defaults))
            st.multiselect(
                "Tags",
                tag_options,
                default=locked_defaults,
                disabled=True,
                key="charts_tags_multiselect_locked",
            )

    if chart_source == "All":
        st.session_state[CHARTS_KEY_FILTER_TAGS] = list(
            st.session_state.get(CHARTS_KEY_TAGS_MULTI) or []
        )

    if subviews:
        slice_state = render_subview_slice_filter(
            all_charts,
            subview_key=CHARTS_KEY_SUBVIEW_TABS,
            slice_key=CHARTS_KEY_SLICE_SELECTOR,
        )
        st.session_state[CHARTS_KEY_FILTER_SUBVIEW] = slice_state.subview
        st.session_state[CHARTS_KEY_FILTER_SLICE_ID] = slice_state.slice_id

    toggle_col1, toggle_col2 = st.columns(2)
    with toggle_col1:
        st.toggle("Expand all sections", key=CHARTS_KEY_EXPAND_ALL)
        sections_expanded = st.session_state.get(CHARTS_KEY_EXPAND_ALL, False)
    with toggle_col2:
        st.toggle(
            "Show Overview",
            key=CHARTS_KEY_SHOW_SUMMARY_TOGGLE,
        )

    show_static = st.session_state.get(CHARTS_KEY_STATIC_TOGGLE, True)
    show_dynamic = st.session_state.get(CHARTS_KEY_DYNAMIC_TOGGLE, True)
    if show_static and show_dynamic:
        kind_filter = None
    elif show_static and not show_dynamic:
        kind_filter = "chart_static"
    elif not show_static and show_dynamic:
        kind_filter = "chart_dynamic"
    else:
        kind_filter = "__none__"

    charts = apply_chart_filters(
        all_charts,
        module=st.session_state.get(CHARTS_KEY_FILTER_MODULE),
        scope=st.session_state.get(CHARTS_KEY_FILTER_SCOPE),
        kind=kind_filter,
        tags=st.session_state.get(CHARTS_KEY_FILTER_TAGS) or None,
        subview=st.session_state.get(CHARTS_KEY_FILTER_SUBVIEW),
        slice_id=st.session_state.get(CHARTS_KEY_FILTER_SLICE_ID),
    )

    if not charts and all_charts and kind_filter != "__none__":
        render_empty_state(
            "filtered_to_zero",
            "No charts match these filters",
            "Try another source preset, clear tags, or use **Reset filters** above.",
            primary_action=("Overview", "Overview"),
            secondary_action=None,
        )

    current_sig = _charts_export_signature(charts)
    stored_result = st.session_state.get(CHARTS_KEY_EXPORT_RESULT)
    stored_sig = st.session_state.get(CHARTS_KEY_EXPORT_SIG)
    export_is_current = _has_current_export(stored_result, stored_sig, current_sig)

    export_col, _ = st.columns([2, 3])
    with export_col:
        if not charts:
            st.caption("No visible charts to export.")
        else:
            if st.button("Export Visible Charts", key="charts_export_btn"):
                try:
                    result = ExportService.zip_charts(
                        run_root, charts, st.session_state.get("run_id", "")
                    )
                    st.session_state[CHARTS_KEY_EXPORT_RESULT] = result
                    st.session_state[CHARTS_KEY_EXPORT_SIG] = current_sig
                    stored_result = result
                    export_is_current = True
                except ValueError as exc:
                    st.error(str(exc))
                    st.session_state.pop(CHARTS_KEY_EXPORT_RESULT, None)
                    st.session_state.pop(CHARTS_KEY_EXPORT_SIG, None)
                    stored_result = None
                    export_is_current = False

            if export_is_current and isinstance(stored_result, ChartsExportResult):
                st.download_button(
                    "Download ZIP",
                    data=stored_result.bytes,
                    file_name=stored_result.filename,
                    mime="application/zip",
                    key="charts_export_download",
                )
                parts = [
                    f"{stored_result.exported_count} chart"
                    + ("s" if stored_result.exported_count != 1 else ""),
                    f"across {stored_result.module_count} module"
                    + ("s" if stored_result.module_count != 1 else ""),
                ]
                if stored_result.omitted_count:
                    parts.append(f"{stored_result.omitted_count} omitted")
                st.caption(" · ".join(parts))

    full_screen_id = st.session_state.get(CHARTS_KEY_FULL_SCREEN)
    if full_screen_id:
        selected = next((a for a in all_charts if a.id == full_screen_id), None)
        if selected:
            st.subheader(selected.title or selected.rel_path)
            selected_description = resolve_chart_description(selected)
            if selected_description:
                st.caption(selected_description)
            elif selected.has_tag("group_aggregate"):
                st.caption(_group_aggregate_semantics_caption(selected))
            if st.button("Close Full Screen"):
                st.session_state[CHARTS_KEY_FULL_SCREEN] = None
                st.rerun()
            if selected.kind == "chart_static":
                path = ArtifactService.resolve_artifact_source_path(run_root, selected)
                if path and path.exists():
                    st.image(Image.open(path), width="stretch")
            else:
                html_payload = ArtifactService.load_html_artifact(run_root, selected)
                if not html_payload:
                    st.error("Unable to load HTML chart.")
                else:
                    size = html_payload["bytes"]
                    if size > MAX_FULLSCREEN_HTML_BYTES:
                        st.warning(
                            "HTML chart is too large to render. Download instead."
                        )
                    else:
                        st.iframe(html_payload["content"], height=700)
        st.divider()

    overview_candidates = _overview_candidate_charts(
        all_charts,
        chart_source,
        list(st.session_state.get(CHARTS_KEY_FILTER_TAGS) or []),
    )
    overview_slots = build_overview_slots(
        overview_candidates=overview_candidates,
        user_overview=user_overview,
        missing_behavior=missing_behavior,
        max_items=max_items,
    )

    overview_chart_count = sum(
        len(slot["artifacts"]) for slot in overview_slots if slot["artifacts"]
    )
    overview_slot_count = len(overview_slots)
    display_overview_count = overview_chart_count or overview_slot_count

    show_summary = st.session_state.get(CHARTS_KEY_SHOW_SUMMARY_TOGGLE, True)
    if overview_slot_count and show_summary:
        with st.expander(
            f"📋 Overview ({display_overview_count} chart{'s' if display_overview_count != 1 else ''})",
            expanded=sections_expanded,
        ):
            for slot in overview_slots:
                st.markdown(f"**{slot['label']}**")
                slot_description = slot.get("description")
                if slot_description:
                    st.caption(slot_description)
                if slot.get("missing"):
                    render_empty_state(
                        "module_unavailable",
                        "Chart not available",
                        "This overview slot has no artifact for this run (module skipped or not configured).",
                        primary_action=("Overview", "Overview"),
                        secondary_action=("Run Analysis", "Run Analysis"),
                    )
                    st.divider()
                    continue
                family = family_from_overview_slot(slot)
                if family:
                    _render_chart_family_section(
                        run_root,
                        family,
                        f"overview_chart_{slot['viz_id']}",
                        sections_expanded=sections_expanded,
                        show_family_expander=False,
                    )
                st.divider()

    module_groups: Dict[str, List[Artifact]] = {}
    for chart in charts:
        module = chart.module or "Other"
        module_groups.setdefault(module, []).append(chart)

    for module_name in order_strings_like_modules(list(module_groups.keys())):
        module_charts = module_groups[module_name]
        with st.expander(
            f"📊 {module_name} ({len(module_charts)} chart{'s' if len(module_charts) != 1 else ''})",
            expanded=sections_expanded,
        ):
            families = group_charts_into_families(module_charts)
            for fi, family in enumerate(families):
                _render_chart_family_section(
                    run_root,
                    family,
                    f"chart_{module_name}_{family.key}",
                    sections_expanded=sections_expanded,
                    show_family_expander=True,
                )
                if fi < len(families) - 1:
                    st.divider()


def _render_charts_body(ctx: RunScopedPageContext) -> None:
    _ensure_charts_filters_for_run(ctx.subject.subject_id, ctx.run_id)

    run_root = ctx.run_root
    all_artifacts = ArtifactService.list_artifacts(run_root)
    all_charts = [
        a for a in all_artifacts if a.kind in {"chart_static", "chart_dynamic"}
    ]

    badge_bits = compute_chart_badges(all_charts)

    render_page_shell(
        "Charts Gallery",
        "Browse static and dynamic chart artifacts for the current run.",
        badges=badge_bits,
        actions=None,
    )

    if not all_charts:
        render_empty_state(
            "no_results_yet",
            "No chart artifacts for this run",
            "This run completed without chart outputs, or charts were not produced for the selected modules.",
            primary_action=("Run Analysis", "Run Analysis"),
            secondary_action=("Overview", "Overview"),
        )
        render_page_help(_CHARTS_HELP_LOADED)
        return

    modules, scopes, tags, subviews = build_filter_options(all_charts)
    resolved = (
        resolve_effective_config(run_dir=run_root)
        if run_root and run_root.exists()
        else resolve_effective_config(run_dir=None)
    )
    if resolved:
        cfg = resolved.effective_config
        dashboard_config = getattr(cfg, "dashboard", None)
    else:
        dashboard_config = None
    user_overview = getattr(dashboard_config, "overview_charts", []) or []
    max_ov_items = getattr(dashboard_config, "overview_max_items", None)
    missing_behavior = getattr(dashboard_config, "overview_missing_behavior", "skip")

    _charts_filters_and_gallery_fragment(
        run_root,
        all_charts,
        modules,
        scopes,
        tags,
        subviews,
        user_overview,
        max_ov_items,
        missing_behavior,
    )
    render_page_help(_CHARTS_HELP_LOADED)


def render_charts() -> None:
    render_run_scoped_page(_CHARTS_CONFIG, render_body=_render_charts_body)
