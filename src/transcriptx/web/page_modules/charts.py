"""
Charts gallery page for TranscriptX Studio.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Sequence

import streamlit as st
from PIL import Image

from transcriptx.core.config import resolve_effective_config
from transcriptx.export import ChartsExportResult
from transcriptx.web.blocks.filters.subview_slice import render_subview_slice_filter
from transcriptx.web.charts_filter_state import (
    chart_text_flags,
    charts_filters_are_dirty,
    ensure_charts_chart_text,
    ensure_charts_scope_filter,
    intersect_charts_open_modules,
    kind_filter_from_session,
    reset_charts_filters_for_run_change,
    reset_charts_filters_to_defaults,
    scope_filter_from_session,
    set_charts_open_modules,
    sync_kind_toggles_from_pills,
)
from transcriptx.web.components.action_links import (
    render_action_link,
    render_download_link,
)
from transcriptx.web.components.empty_state import render_empty_state
from transcriptx.web.components.page_shell import render_page_shell
from transcriptx.web.components.run_scoped_page import (
    RunScopedPageConfig,
    RunScopedPageContext,
    render_run_scoped_page,
)
from transcriptx.web.models.artifact import Artifact
from transcriptx.web.module_option_format import format_module_option
from transcriptx.web.services import ArtifactService
from transcriptx.web.services.artifact_service import (
    MAX_FULLSCREEN_HTML_BYTES,
    MAX_INLINE_HTML_BYTES,
)
from transcriptx.core.llm_feedback.models import (
    FeedbackSurface,
    FeedbackTarget,
)
from transcriptx.web.components.llm_feedback import render_llm_feedback_controls
from transcriptx.web.services.chart_llm_description import (
    logical_chart_id_for_gallery_artifact,
    resolve_chart_llm_description,
)
from transcriptx.web.services.llm_feedback_service import get_llm_feedback_service
from transcriptx.web.services.chart_view_model_service import (
    ChartGalleryFamily,
    ChartModuleGroupCounts,
    build_charts_gallery_view,
    build_filter_options,
    compute_chart_badges,
    family_from_overview_slot,
    group_charts_into_families,
    resolve_chart_display_description,
)
from transcriptx.web.services.export_service import ExportService
from transcriptx.web.speaker_accent import load_accent_resolve_context, speaker_expander
from transcriptx.web.state import (
    CHARTS_CHART_TEXT_BOTH,
    CHARTS_CHART_TEXT_DESCRIPTION,
    CHARTS_CHART_TEXT_LLM,
    CHARTS_CHART_TEXT_NONE,
    CHARTS_KEY_CHART_TEXT,
    CHARTS_KEY_EXPORT_RESULT,
    CHARTS_KEY_EXPORT_SIG,
    CHARTS_KEY_FILTERS_INIT,
    CHARTS_KEY_FILTER_MODULE,
    CHARTS_KEY_FILTER_SCOPE,
    CHARTS_KEY_FILTER_SLICE_ID,
    CHARTS_KEY_FILTER_SUBVIEW,
    CHARTS_KEY_FILTER_TAGS,
    CHARTS_KEY_FULL_SCREEN,
    CHARTS_KEY_KIND_PILLS,
    CHARTS_KEY_MODULE_SORT,
    CHARTS_KEY_OPEN_MODULES,
    CHARTS_KEY_SEARCH,
    CHARTS_KEY_SECTION,
    CHARTS_KEY_SLICE_SELECTOR,
    CHARTS_KEY_SOURCE_PRESET,
    CHARTS_KEY_SUBVIEW_TABS,
    CHARTS_KEY_TAGS_MULTI,
    CHARTS_KIND_DYNAMIC,
    CHARTS_KIND_STATIC,
    CHARTS_SECTION_BROWSE,
    CHARTS_SECTION_OVERVIEW,
    CHARTS_SORT_ALPHA,
    CHARTS_SORT_MODULE_FAMILY,
    SELECTBOX_PLACEHOLDER_MODULE,
)

_CHARTS_SECTIONS = (CHARTS_SECTION_OVERVIEW, CHARTS_SECTION_BROWSE)
_SECTION_CONTROL_KEY = "charts_section_control"
_SECTION_RADIO_KEY = "charts_section_radio"

_CHARTS_CONFIG = RunScopedPageConfig(
    title="Charts Gallery",
    description=(
        "Select a subject and run in the sidebar if the gallery is empty."
    ),
    empty_headline="No subject or run selected",
    empty_detail="Pick a transcript or group and a run in the sidebar to view charts.",
    primary_action=("Open Library", "Library"),
    secondary_action=("Run Analysis", "Run Analysis"),
)

_SOURCE_HELP = (
    "Member session charts are merged from each transcript run in the group; "
    "group aggregate charts summarize the whole group."
)

_CHART_TEXT_OPTIONS = (
    CHARTS_CHART_TEXT_NONE,
    CHARTS_CHART_TEXT_DESCRIPTION,
    CHARTS_CHART_TEXT_LLM,
    CHARTS_CHART_TEXT_BOTH,
)

_SORT_LABELS = {
    CHARTS_SORT_MODULE_FAMILY: "Module family",
    CHARTS_SORT_ALPHA: "A–Z",
}


_CHARTS_FB_RUN_ID = "_charts_fb_run_id"
_CHARTS_FB_SUBJECT_ID = "_charts_fb_subject_id"
_CHARTS_FB_SUBJECT_TYPE = "_charts_fb_subject_type"


def _render_chart_llm_feedback(chart: Artifact, llm_text: str, *, key: str) -> None:
    run_id = str(st.session_state.get(_CHARTS_FB_RUN_ID) or "").strip()
    subject_id = str(st.session_state.get(_CHARTS_FB_SUBJECT_ID) or "").strip()
    subject_type = str(st.session_state.get(_CHARTS_FB_SUBJECT_TYPE) or "transcript")
    logical_id = logical_chart_id_for_gallery_artifact(chart)
    if not run_id or not subject_id or not logical_id or not llm_text.strip():
        return
    target = FeedbackTarget(
        surface=FeedbackSurface.CHART_CAPTION.value,
        block_id=None,
        placement_id=None,
        module="chart_descriptions",
        run_id=run_id,
        subject_type="group" if subject_type == "group" else "transcript",
        subject_id=subject_id,
        artifact_rel_path=str(chart.rel_path or "") or None,
        question_id=None,
        questions_hash=None,
        logical_chart_id=logical_id,
    )
    render_llm_feedback_controls(
        store=get_llm_feedback_service(),
        target=target,
        output_text=llm_text,
        provenance=None,
        widget_key=key,
    )


def _render_chart_gallery_card(
    run_root: Path,
    chart: Artifact,
    button_key: str,
    *,
    show_registry_description: bool = True,
    show_llm_summary: bool = True,
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
        if show_registry_description:
            description = resolve_chart_display_description(chart)
            if description:
                st.caption(description)
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
        if show_llm_summary:
            llm_text = resolve_chart_llm_description(run_root, chart)
            if llm_text:
                st.markdown(llm_text)
                _render_chart_llm_feedback(
                    chart, llm_text, key=f"fb_chart_{button_key}"
                )


def _render_chart_card_grid(
    run_root: Path,
    artifacts: list[Artifact],
    key_prefix: str,
    *,
    show_registry_description: bool = True,
    show_llm_summary: bool = True,
) -> None:
    cols = st.columns(3)
    for idx, chart in enumerate(artifacts):
        with cols[idx % 3]:
            _render_chart_gallery_card(
                run_root,
                chart,
                f"{key_prefix}_{chart.id}_{idx}",
                show_registry_description=show_registry_description,
                show_llm_summary=show_llm_summary,
            )


def _family_renders_directly(family: ChartGalleryFamily) -> bool:
    return family.cardinality in {"single", "paired_static_dynamic"} or (
        len(family.slices) == 1 and family.slices[0].key == "all"
    )


def _slice_is_speaker(family: ChartGalleryFamily, slice_artifacts: list) -> bool:
    if family.cardinality == "speaker_set":
        return True
    return any(
        getattr(artifact, "subview", None) == "by_speaker"
        or getattr(artifact, "scope", None) == "speaker"
        for artifact in slice_artifacts
    )


def _render_chart_family_slices(
    run_root: Path,
    family: ChartGalleryFamily,
    key_prefix: str,
    *,
    sections_expanded: bool,
    show_registry_description: bool = True,
    show_llm_summary: bool = True,
) -> None:
    if _family_renders_directly(family):
        artifacts = family.slices[0].artifacts if family.slices else []
        _render_chart_card_grid(
            run_root,
            artifacts,
            key_prefix,
            show_registry_description=show_registry_description,
            show_llm_summary=show_llm_summary,
        )
        return

    accent_ctx = load_accent_resolve_context()
    for sl in family.slices:
        if not sl.label:
            _render_chart_card_grid(
                run_root,
                sl.artifacts,
                f"{key_prefix}_{sl.key}",
                show_registry_description=show_registry_description,
                show_llm_summary=show_llm_summary,
            )
            continue
        meta = str(len(sl.artifacts))
        if _slice_is_speaker(family, sl.artifacts):
            section = speaker_expander(
                sl.label,
                meta=meta,
                expanded=sections_expanded,
                context=accent_ctx,
            )
        else:
            section = st.expander(
                f"{sl.label} ({meta})",
                expanded=sections_expanded,
            )
        with section:
            st.markdown('<div class="tx-chart-slice-shell">', unsafe_allow_html=True)
            _render_chart_card_grid(
                run_root,
                sl.artifacts,
                f"{key_prefix}_{sl.key}",
                show_registry_description=show_registry_description,
                show_llm_summary=show_llm_summary,
            )
            st.markdown("</div>", unsafe_allow_html=True)


def _render_chart_family_section(
    run_root: Path,
    family: ChartGalleryFamily,
    key_prefix: str,
    *,
    sections_expanded: bool,
    show_family_expander: bool = True,
    show_registry_description: bool = True,
    show_llm_summary: bool = True,
) -> None:
    if show_family_expander:
        with st.expander(
            f"{family.label} ({family.artifact_count})",
            expanded=sections_expanded,
        ):
            if family.description and show_registry_description:
                st.caption(family.description)
            st.markdown('<div class="tx-chart-family-shell">', unsafe_allow_html=True)
            _render_chart_family_slices(
                run_root,
                family,
                key_prefix,
                sections_expanded=sections_expanded,
                show_registry_description=show_registry_description,
                show_llm_summary=show_llm_summary,
            )
            st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown('<div class="tx-chart-family-shell">', unsafe_allow_html=True)
        _render_chart_family_slices(
            run_root,
            family,
            key_prefix,
            sections_expanded=sections_expanded,
            show_registry_description=show_registry_description,
            show_llm_summary=show_llm_summary,
        )
        st.markdown("</div>", unsafe_allow_html=True)


def _ensure_charts_filters_for_run(subject_id: str, run_id: str) -> None:
    marker = st.session_state.get(CHARTS_KEY_FILTERS_INIT)
    identity = f"{subject_id}|{run_id}"
    if marker != identity:
        reset_charts_filters_for_run_change(st.session_state)
        st.session_state[CHARTS_KEY_FILTERS_INIT] = identity
    ensure_charts_chart_text(st.session_state)


def _charts_export_signature(charts: list[Artifact]) -> frozenset[str]:
    return frozenset(a.id for a in charts)


def _has_current_export(
    stored_result: object, stored_sig: object, current_sig: frozenset[str]
) -> bool:
    return isinstance(stored_result, ChartsExportResult) and stored_sig == current_sig


def _fragment_rerun() -> None:
    try:
        st.rerun(scope="fragment")
    except TypeError:
        st.rerun()


def _apply_source_tag_coupling(chart_source: str) -> None:
    """Force source tags and clear incompatible free-form tag selections."""
    if chart_source == "Group aggregate":
        st.session_state[CHARTS_KEY_FILTER_TAGS] = ["group_aggregate"]
        st.session_state[CHARTS_KEY_TAGS_MULTI] = []
    elif chart_source == "Member sessions":
        st.session_state[CHARTS_KEY_FILTER_TAGS] = ["member_session"]
        st.session_state[CHARTS_KEY_TAGS_MULTI] = []
    else:
        # Free-form tags only apply when Source is All.
        st.session_state[CHARTS_KEY_FILTER_TAGS] = list(
            st.session_state.get(CHARTS_KEY_TAGS_MULTI) or []
        )


def _toggle_module_open(module_id: str) -> None:
    current = list(st.session_state.get(CHARTS_KEY_OPEN_MODULES) or [])
    if module_id in current:
        set_charts_open_modules(
            st.session_state, [mid for mid in current if mid != module_id]
        )
    else:
        set_charts_open_modules(st.session_state, current + [module_id])
    _fragment_rerun()


def _render_module_row(
    run_root: Path,
    group: ChartModuleGroupCounts,
    *,
    is_open: bool,
    show_registry_description: bool,
    show_llm_summary: bool,
) -> None:
    chevron = "▾" if is_open else "›"
    count = f"{group.total} chart{'s' if group.total != 1 else ''}"
    label = f"{chevron}  {group.display_name}  ·  {count}"
    st.markdown('<div class="tx-chart-module-row">', unsafe_allow_html=True)
    if st.button(
        label,
        key=f"charts_module_toggle_{group.module_id}",
        use_container_width=True,
        type="secondary",
    ):
        _toggle_module_open(group.module_id)
    st.markdown("</div>", unsafe_allow_html=True)

    if not is_open:
        return

    families = group_charts_into_families(group.charts)
    for fi, family in enumerate(families):
        _render_chart_family_section(
            run_root,
            family,
            f"chart_{group.module_id}_{family.key}",
            sections_expanded=False,
            show_family_expander=True,
            show_registry_description=show_registry_description,
            show_llm_summary=show_llm_summary,
        )
        if fi < len(families) - 1:
            st.divider()


def _render_view_options_popover(visible_module_ids: list[str]) -> None:
    ensure_charts_chart_text(st.session_state)
    with st.popover("More view options"):
        st.segmented_control(
            "Chart text",
            options=list(_CHART_TEXT_OPTIONS),
            key=CHARTS_KEY_CHART_TEXT,
        )
        expand_col, collapse_col = st.columns(2)
        with expand_col:
            if st.button("Expand visible", key="charts_expand_visible"):
                ids = list(
                    visible_module_ids
                    or st.session_state.get("_charts_visible_module_ids")
                    or []
                )
                set_charts_open_modules(st.session_state, ids)
                _fragment_rerun()
        with collapse_col:
            if st.button("Collapse all", key="charts_collapse_all"):
                set_charts_open_modules(st.session_state, [])
                _fragment_rerun()


def _run_export_visible(run_root: Path, filtered_charts: list[Artifact]) -> None:
    current_sig = _charts_export_signature(filtered_charts)
    try:
        result = ExportService.zip_charts(
            run_root, filtered_charts, st.session_state.get("run_id", "")
        )
        st.session_state[CHARTS_KEY_EXPORT_RESULT] = result
        st.session_state[CHARTS_KEY_EXPORT_SIG] = current_sig
    except ValueError as exc:
        st.error(str(exc))
        st.session_state.pop(CHARTS_KEY_EXPORT_RESULT, None)
        st.session_state.pop(CHARTS_KEY_EXPORT_SIG, None)


def _render_export_under_badges(
    run_root: Path,
    filtered_charts: list[Artifact],
) -> None:
    current_sig = _charts_export_signature(filtered_charts)
    stored_result = st.session_state.get(CHARTS_KEY_EXPORT_RESULT)
    stored_sig = st.session_state.get(CHARTS_KEY_EXPORT_SIG)
    export_is_current = _has_current_export(stored_result, stored_sig, current_sig)

    if not filtered_charts:
        st.caption("No visible charts to export.")
        return

    if render_action_link(
        "Export visible",
        key="charts_export_visible",
        icon=":material/folder_zip:",
        help="Zip the charts matching the current filters",
    ):
        _run_export_visible(run_root, filtered_charts)
        stored_result = st.session_state.get(CHARTS_KEY_EXPORT_RESULT)
        stored_sig = st.session_state.get(CHARTS_KEY_EXPORT_SIG)
        export_is_current = _has_current_export(stored_result, stored_sig, current_sig)

    if export_is_current and isinstance(stored_result, ChartsExportResult):
        render_download_link(
            "Download ZIP",
            data=stored_result.bytes,
            file_name=stored_result.filename,
            mime="application/zip",
            key="charts_export_download",
            icon=":material/download:",
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


def _render_filter_toolbar(visible_module_ids: list[str]) -> None:
    dirty = charts_filters_are_dirty(st.session_state)
    st.markdown('<div class="tx-charts-filter-toolbar">', unsafe_allow_html=True)
    if dirty:
        reset_col, options_col, _ = st.columns([0.9, 1.5, 4.5])
        with reset_col:
            if st.button("Reset", key="charts_reset_filters", width="content"):
                reset_charts_filters_to_defaults(st.session_state)
                _fragment_rerun()
        with options_col:
            _render_view_options_popover(visible_module_ids)
    else:
        options_col, _ = st.columns([1.5, 5.5])
        with options_col:
            _render_view_options_popover(visible_module_ids)
    st.markdown("</div>", unsafe_allow_html=True)


def _current_sort_mode() -> str:
    sort_mode = st.session_state.get(CHARTS_KEY_MODULE_SORT, CHARTS_SORT_MODULE_FAMILY)
    if sort_mode not in {CHARTS_SORT_MODULE_FAMILY, CHARTS_SORT_ALPHA}:
        sort_mode = CHARTS_SORT_MODULE_FAMILY
        st.session_state[CHARTS_KEY_MODULE_SORT] = sort_mode
    return str(sort_mode)


def _seed_section_widget(key: str, current: str, labels: Sequence[str]) -> None:
    if key not in st.session_state or st.session_state.get(key) not in labels:
        st.session_state[key] = current


def _render_section_nav(*, has_overview: bool) -> str:
    labels = list(_CHARTS_SECTIONS)
    default = (
        CHARTS_SECTION_OVERVIEW if has_overview else CHARTS_SECTION_BROWSE
    )
    current = st.session_state.get(CHARTS_KEY_SECTION, default)
    if current not in labels:
        current = default
        st.session_state[CHARTS_KEY_SECTION] = current
    if not has_overview and current == CHARTS_SECTION_OVERVIEW:
        current = CHARTS_SECTION_BROWSE
        st.session_state[CHARTS_KEY_SECTION] = current
    _seed_section_widget(_SECTION_CONTROL_KEY, current, labels)
    try:
        choice = st.segmented_control(
            "Charts section",
            options=labels,
            key=_SECTION_CONTROL_KEY,
            label_visibility="collapsed",
        )
    except Exception:
        _seed_section_widget(_SECTION_RADIO_KEY, current, labels)
        choice = st.radio(
            "Charts section",
            labels,
            horizontal=True,
            key=_SECTION_RADIO_KEY,
            label_visibility="collapsed",
        )
    if choice not in labels:
        choice = current
    st.session_state[CHARTS_KEY_SECTION] = choice
    return str(choice)


def _build_view_from_session(
    all_charts: list[Artifact],
    *,
    user_overview: Sequence[Any],
    missing_behavior: str,
    max_items: Optional[int],
):
    chart_source = st.session_state.get(CHARTS_KEY_SOURCE_PRESET, "All") or "All"
    _apply_source_tag_coupling(chart_source)
    sync_kind_toggles_from_pills(st.session_state)
    ensure_charts_scope_filter(st.session_state)
    return build_charts_gallery_view(
        all_charts,
        module=st.session_state.get(CHARTS_KEY_FILTER_MODULE),
        scope=scope_filter_from_session(st.session_state),
        kind=kind_filter_from_session(st.session_state),
        tags=st.session_state.get(CHARTS_KEY_FILTER_TAGS) or None,
        subview=st.session_state.get(CHARTS_KEY_FILTER_SUBVIEW),
        slice_id=st.session_state.get(CHARTS_KEY_FILTER_SLICE_ID),
        search=st.session_state.get(CHARTS_KEY_SEARCH) or "",
        sort_mode=_current_sort_mode(),
        user_overview=user_overview,
        missing_behavior=missing_behavior,
        max_items=max_items,
    )


def _sync_derived_filter_keys() -> None:
    """Align derived filter keys with widget keys before building the view."""
    chart_source = st.session_state.get(CHARTS_KEY_SOURCE_PRESET, "All") or "All"
    _apply_source_tag_coupling(chart_source)
    ensure_charts_scope_filter(st.session_state)
    sync_kind_toggles_from_pills(st.session_state)

    tab = st.session_state.get(CHARTS_KEY_SUBVIEW_TABS, "All")
    subview = None if not tab or tab == "All" else str(tab)
    slice_choice = st.session_state.get(CHARTS_KEY_SLICE_SELECTOR, "All")
    slice_id = (
        None if not slice_choice or slice_choice == "All" else str(slice_choice)
    )
    st.session_state[CHARTS_KEY_FILTER_SUBVIEW] = subview
    st.session_state[CHARTS_KEY_FILTER_SLICE_ID] = slice_id


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
    _sync_derived_filter_keys()

    view = _build_view_from_session(
        all_charts,
        user_overview=user_overview,
        missing_behavior=missing_behavior,
        max_items=max_items,
    )
    visible_module_ids = [g.module_id for g in view.module_groups]
    st.session_state["_charts_visible_module_ids"] = list(visible_module_ids)
    open_modules = intersect_charts_open_modules(
        st.session_state, frozenset(visible_module_ids)
    )
    chart_text = ensure_charts_chart_text(st.session_state)
    show_registry_description, show_llm_summary = chart_text_flags(str(chart_text))

    render_page_shell(
        "Charts Gallery",
        None,
        badges=compute_chart_badges(all_charts),
        actions=None,
        extra=lambda: _render_export_under_badges(run_root, view.filtered_charts),
    )

    st.text_input("Search charts…", key=CHARTS_KEY_SEARCH)

    scope_options = ["All"] + list(scopes)
    current_scope = st.session_state.get(CHARTS_KEY_FILTER_SCOPE, "All")
    if current_scope not in scope_options:
        st.session_state[CHARTS_KEY_FILTER_SCOPE] = "All"

    row1a, row1b, row1c = st.columns([1.6, 1.4, 1.2])
    with row1a:
        st.segmented_control(
            "Source",
            options=["All", "Group aggregate", "Member sessions"],
            key=CHARTS_KEY_SOURCE_PRESET,
            help=_SOURCE_HELP,
        )
    with row1b:
        st.segmented_control(
            "Scope",
            options=scope_options,
            key=CHARTS_KEY_FILTER_SCOPE,
        )
    with row1c:
        st.pills(
            "Type",
            options=[CHARTS_KIND_STATIC, CHARTS_KIND_DYNAMIC],
            selection_mode="multi",
            key=CHARTS_KEY_KIND_PILLS,
        )
        sync_kind_toggles_from_pills(st.session_state)

    chart_source = st.session_state.get(CHARTS_KEY_SOURCE_PRESET, "All") or "All"
    _apply_source_tag_coupling(chart_source)

    row2a, row2b = st.columns([1.4, 2.0])
    with row2a:
        st.selectbox(
            "Module",
            [None] + modules,
            format_func=lambda m: (
                SELECTBOX_PLACEHOLDER_MODULE if m is None else format_module_option(m)
            ),
            key=CHARTS_KEY_FILTER_MODULE,
        )
    with row2b:
        if chart_source == "All":
            st.multiselect("Tags", tags, key=CHARTS_KEY_TAGS_MULTI)
            st.session_state[CHARTS_KEY_FILTER_TAGS] = list(
                st.session_state.get(CHARTS_KEY_TAGS_MULTI) or []
            )
        else:
            locked_defaults = list(st.session_state.get(CHARTS_KEY_FILTER_TAGS) or [])
            tag_options = sorted(set(tags) | set(locked_defaults))
            locked_key = "charts_tags_multiselect_locked"
            if st.session_state.get(locked_key) != locked_defaults:
                st.session_state[locked_key] = locked_defaults
            st.multiselect(
                "Tags",
                tag_options,
                disabled=True,
                key=locked_key,
            )

    if subviews:
        slice_state = render_subview_slice_filter(
            all_charts,
            subview_key=CHARTS_KEY_SUBVIEW_TABS,
            slice_key=CHARTS_KEY_SLICE_SELECTOR,
        )
        st.session_state[CHARTS_KEY_FILTER_SUBVIEW] = slice_state.subview
        st.session_state[CHARTS_KEY_FILTER_SLICE_ID] = slice_state.slice_id

    _render_filter_toolbar(visible_module_ids)

    if not view.filtered_charts and all_charts:
        render_empty_state(
            "filtered_to_zero",
            "No charts match these filters",
            "Try another source, clear search or tags, or use **Reset**.",
            primary_action=("Overview", "Overview"),
            secondary_action=None,
        )

    full_screen_id = st.session_state.get(CHARTS_KEY_FULL_SCREEN)
    if full_screen_id:
        selected = next((a for a in all_charts if a.id == full_screen_id), None)
        if selected:
            st.subheader(selected.title or selected.rel_path)
            if show_registry_description:
                selected_description = resolve_chart_display_description(selected)
                if selected_description:
                    st.caption(selected_description)
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
            if show_llm_summary:
                llm_text = resolve_chart_llm_description(run_root, selected)
                if llm_text:
                    st.markdown(llm_text)
                    _render_chart_llm_feedback(
                        selected, llm_text, key=f"fb_chart_fs_{selected.id}"
                    )
        st.divider()

    section = _render_section_nav(has_overview=bool(view.overview_slots))

    if section == CHARTS_SECTION_OVERVIEW:
        if not view.overview_slots:
            st.caption("No overview slots for the current filters.")
        else:
            for slot in view.overview_slots:
                st.markdown(f"**{slot['label']}**")
                slot_description = slot.get("description")
                if slot_description and show_registry_description:
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
                        sections_expanded=False,
                        show_family_expander=False,
                        show_registry_description=show_registry_description,
                        show_llm_summary=show_llm_summary,
                    )
                st.divider()
        return

    st.caption(f"{view.matching_count} matching")
    st.segmented_control(
        "Sort",
        options=[CHARTS_SORT_MODULE_FAMILY, CHARTS_SORT_ALPHA],
        format_func=lambda k: _SORT_LABELS.get(k, k),
        key=CHARTS_KEY_MODULE_SORT,
    )

    for group in view.module_groups:
        _render_module_row(
            run_root,
            group,
            is_open=group.module_id in open_modules,
            show_registry_description=show_registry_description,
            show_llm_summary=show_llm_summary,
        )


def _render_charts_body(ctx: RunScopedPageContext) -> None:
    _ensure_charts_filters_for_run(ctx.subject.subject_id, ctx.run_id)
    st.session_state[_CHARTS_FB_RUN_ID] = ctx.run_id
    st.session_state[_CHARTS_FB_SUBJECT_ID] = ctx.subject.subject_id
    st.session_state[_CHARTS_FB_SUBJECT_TYPE] = ctx.subject.subject_type

    run_root = ctx.run_root
    all_artifacts = ArtifactService.list_artifacts(run_root)
    all_charts = [
        a for a in all_artifacts if a.kind in {"chart_static", "chart_dynamic"}
    ]

    if not all_charts:
        render_page_shell(
            "Charts Gallery",
            None,
            badges=compute_chart_badges(all_charts),
            actions=None,
        )
        render_empty_state(
            "no_results_yet",
            "No chart artifacts for this run",
            "This run completed without chart outputs, or charts were not produced for the selected modules.",
            primary_action=("Run Analysis", "Run Analysis"),
            secondary_action=("Overview", "Overview"),
        )
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


def render_charts() -> None:
    render_run_scoped_page(_CHARTS_CONFIG, render_body=_render_charts_body)
