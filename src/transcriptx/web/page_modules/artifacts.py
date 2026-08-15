"""
Merged Artifacts page: Browse | Preview | Export (conditional sections).
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from transcriptx.web.blocks.implementations.data import render_artifact_file_preview
from transcriptx.web.components.info_tooltip import widget_help
from transcriptx.web.components.action_links import render_action_link
from transcriptx.web.components.export_panel import render_export_panel_ui
from transcriptx.web.components.page_shell import render_page_shell
from transcriptx.web.components.run_scoped_page import (
    RunScopedPageConfig,
    RunScopedPageContext,
    render_run_scoped_page,
)
from transcriptx.web.services.artifact_index import (
    ArtifactSourceFilter,
    build_artifact_index,
    filter_by_source,
    order_artifacts_for_browse,
)
from transcriptx.web.services import ArtifactService
from transcriptx.web.state import (
    ARTIFACTS_KEY_PREVIEW_ID,
    ARTIFACTS_KEY_SECTION,
    ARTIFACTS_KEY_SELECTED_IDS,
    ARTIFACTS_KEY_SHOW_MORE,
    ARTIFACTS_KEY_SOURCE_FILTER,
    DATA_KEY_ARTIFACT_PRESET,
    SELECTBOX_PLACEHOLDER_ARTIFACT,
    consume_artifact_preset,
    reconcile_artifact_selection,
)

ARTIFACTS_SECTIONS = (
    ("Browse", "Browse"),
    ("Preview", "Preview"),
    ("Export", "Export"),
)

BROWSE_PAGE_SIZE = 75

_SECTION_CONTROL_KEY = "artifacts_section_control"
_SECTION_RADIO_KEY = "artifacts_section_radio"
_PREVIEW_SELECTOR_KEY = "artifacts_preview_selector"

_ARTIFACTS_CONFIG = RunScopedPageConfig(
    title="Artifacts",
    description=(
        "Browse, preview, and export run outputs grouped by presentation taxonomy."
    ),
    empty_headline="Select a subject and run",
    empty_detail="Pick a transcript or group and run in the sidebar.",
    primary_action=("Open Library", "Library"),
    secondary_action=("Overview", "Overview"),
)


def _sync_preview_nav_widgets(artifact_id: str | None = None) -> None:
    """Write keyed nav/select values. Must run before those widgets instantiate."""
    st.session_state[_SECTION_CONTROL_KEY] = "Preview"
    st.session_state[_SECTION_RADIO_KEY] = "Preview"
    if artifact_id:
        st.session_state[_PREVIEW_SELECTOR_KEY] = artifact_id


def _open_artifact_preview(artifact_id: str, *, defer_widgets: bool = False) -> None:
    """Switch to Preview and preselect an artifact (logical + widget keys).

    Streamlit keyed widgets ignore default=/index= once the key exists, so
    programmatic navigation must write the widget keys directly — but only
    before they are instantiated. Mid-script jumps (Browse→Preview) must
    defer widget writes to the next run via ``_artifacts_force_preview``.
    """
    st.session_state[ARTIFACTS_KEY_PREVIEW_ID] = artifact_id
    st.session_state[ARTIFACTS_KEY_SECTION] = "Preview"
    if defer_widgets:
        st.session_state["_artifacts_force_preview"] = True
        return
    _sync_preview_nav_widgets(artifact_id)


def _force_preview_section() -> None:
    """Honor one-shot deep links / Browse→Preview jumps against keyed nav widgets."""
    preset = st.session_state.get(DATA_KEY_ARTIFACT_PRESET) or st.session_state.get(
        ARTIFACTS_KEY_PREVIEW_ID
    )
    if preset:
        _open_artifact_preview(str(preset))
    else:
        st.session_state[ARTIFACTS_KEY_SECTION] = "Preview"
        _sync_preview_nav_widgets()
    st.session_state.pop("_artifacts_force_preview", None)


def _seed_section_widget(key: str, current: str, labels: list[str]) -> None:
    """Initialize or repair a keyed nav widget without pairing default=/index=."""
    # Streamlit warns if a widget key is written via Session State *and* default=
    # (or index=) is passed on the same instantiation. Programmatic Preview jumps
    # write these keys before the widget exists, so seed here and omit defaults.
    if key not in st.session_state or st.session_state.get(key) not in labels:
        st.session_state[key] = current


def _section_nav() -> str:
    labels = [lab for _, lab in ARTIFACTS_SECTIONS]
    current = st.session_state.get(ARTIFACTS_KEY_SECTION, "Browse")
    if current not in labels:
        current = "Browse"
        st.session_state[ARTIFACTS_KEY_SECTION] = current
    _seed_section_widget(_SECTION_CONTROL_KEY, current, labels)
    try:
        choice = st.segmented_control(
            "Artifacts section",
            options=labels,
            key=_SECTION_CONTROL_KEY,
            label_visibility="collapsed",
        )
    except Exception:
        _seed_section_widget(_SECTION_RADIO_KEY, current, labels)
        choice = st.radio(
            "Artifacts section",
            labels,
            horizontal=True,
            key=_SECTION_RADIO_KEY,
            label_visibility="collapsed",
        )
    st.session_state[ARTIFACTS_KEY_SECTION] = choice
    return choice


def _render_browse(ctx: RunScopedPageContext) -> None:
    index = build_artifact_index(
        ctx.run_root,
        subject_scope=ctx.subject.subject_type,
        subject_id=ctx.subject.subject_id,
        run_id=ctx.run_id,
    )
    is_group = (ctx.run_root / "group_member_runs.json").exists()
    source_options = ["All sources"]
    if is_group:
        source_options = ["All sources", "Group aggregate", "Member sessions"]

    source_label = st.selectbox(
        "Source",
        source_options,
        key=ARTIFACTS_KEY_SOURCE_FILTER,
        help=widget_help(
            (
                "For group runs: Group aggregate = pooled artifacts; "
                "Member sessions = per-transcript outputs."
                if is_group
                else "Filter browse list by artifact provenance when available."
            )
        ),
    )
    source_filter = ArtifactSourceFilter.ALL
    if source_label == "Group aggregate":
        source_filter = ArtifactSourceFilter.GROUP_AGGREGATE
    elif source_label == "Member sessions":
        source_filter = ArtifactSourceFilter.MEMBER_SESSIONS

    query = st.text_input(
        "Search",
        key="artifacts_browse_search",
        placeholder="Filter by path, module, title…",
    )
    entries = filter_by_source(index.entries, source_filter)
    entries = order_artifacts_for_browse(entries)
    if query:
        q = query.casefold()
        entries = [
            e
            for e in entries
            if q in (e.artifact.rel_path or "").casefold()
            or q in (e.artifact.module or "").casefold()
            or q in (e.artifact.title or "").casefold()
            or q in (e.member_session or "").casefold()
        ]

    selected = list(st.session_state.get(ARTIFACTS_KEY_SELECTED_IDS) or [])
    show_n = int(st.session_state.get(ARTIFACTS_KEY_SHOW_MORE) or BROWSE_PAGE_SIZE)
    visible = entries[:show_n]

    st.caption(f"{len(entries)} artifacts · showing {len(visible)}")
    for entry in visible:
        a = entry.artifact
        cols = st.columns([0.08, 0.52, 0.2, 0.2])
        with cols[0]:
            checked = st.checkbox(
                "select",
                value=a.id in selected,
                key=f"art_sel_{a.id}",
                label_visibility="collapsed",
            )
            if checked and a.id not in selected:
                selected.append(a.id)
            elif not checked and a.id in selected:
                selected = [i for i in selected if i != a.id]
        with cols[1]:
            title = a.title or Path(a.rel_path).name
            provenance = ""
            if entry.member_session:
                provenance = f" · {entry.member_session}"
            elif entry.source_kind == "group_aggregate":
                provenance = " · group aggregate"
            st.markdown(f"**{title}**")
            st.caption(
                f"{entry.presentation_group_title} · {a.module or '—'} · "
                f"{entry.artifact_role}{provenance}"
            )
            st.caption(a.rel_path)
        with cols[2]:
            st.caption(entry.size_label)
        with cols[3]:
            if entry.preview_eligible and render_action_link(
                "Preview",
                key=f"art_prev_{a.id}",
                icon=":material/visibility:",
            ):
                # Section nav widgets already exist this run — defer widget sync.
                _open_artifact_preview(a.id, defer_widgets=True)
                st.rerun()

    st.session_state[ARTIFACTS_KEY_SELECTED_IDS] = selected

    if len(entries) > show_n:
        if st.button("Show more", key="artifacts_show_more_btn"):
            st.session_state[ARTIFACTS_KEY_SHOW_MORE] = show_n + BROWSE_PAGE_SIZE
            st.rerun()

    with st.expander("On disk but not in manifest", expanded=False):
        st.caption("Advanced: scans the run directory for orphan files.")
        if st.checkbox(
            "Scan for orphan files",
            key="artifacts_orphan_scan",
            help=widget_help(
                "List files under the run directory that are not in the artifact manifest."
            ),
        ):
            _render_orphan_files(ctx.run_root, index.artifacts())


def _render_orphan_files(run_root: Path, catalog_artifacts) -> None:
    """Lazy orphan scan — only when advanced subsection is opened."""
    catalog_rels = {a.rel_path for a in catalog_artifacts}
    files = [p for p in run_root.rglob("*") if p.is_file()]
    orphans = []
    for path in files:
        rel = path.relative_to(run_root).as_posix()
        if rel in catalog_rels:
            continue
        if rel.startswith(".transcriptx/"):
            continue
        orphans.append(path)
    if not orphans:
        st.caption("No orphan files found.")
        return
    for path in orphans[:100]:
        rel = path.relative_to(run_root).as_posix()
        st.text(rel)


def _render_preview(ctx: RunScopedPageContext) -> None:
    index = build_artifact_index(
        ctx.run_root,
        subject_scope=ctx.subject.subject_type,
        subject_id=ctx.subject.subject_id,
        run_id=ctx.run_id,
    )
    previewable = [
        e for e in order_artifacts_for_browse(index.entries) if e.preview_eligible
    ]
    options = {
        e.id: f"{e.artifact.module or 'other'} • {e.artifact.rel_path}"
        for e in previewable
    }
    preset = consume_artifact_preset(st.session_state)
    if preset and preset in options:
        st.session_state[ARTIFACTS_KEY_PREVIEW_ID] = preset
        # Keyed selectbox ignores index= once present; write the widget key
        # before instantiate (same rule as _sync_preview_nav_widgets).
        st.session_state[_PREVIEW_SELECTOR_KEY] = preset

    current = st.session_state.get(ARTIFACTS_KEY_PREVIEW_ID) or ""
    keys = list(options.keys())
    choices = [""] + keys
    desired = current if current in options else ""
    _seed_section_widget(_PREVIEW_SELECTOR_KEY, desired, choices)
    selected_id = st.selectbox(
        "Select artifact",
        choices,
        format_func=lambda k: (
            SELECTBOX_PLACEHOLDER_ARTIFACT if k == "" else options.get(k, k)
        ),
        key=_PREVIEW_SELECTOR_KEY,
    )
    if selected_id:
        st.session_state[ARTIFACTS_KEY_PREVIEW_ID] = selected_id
        # Carry into export selection when practical
        selected = list(st.session_state.get(ARTIFACTS_KEY_SELECTED_IDS) or [])
        if selected_id not in selected:
            selected.append(selected_id)
            st.session_state[ARTIFACTS_KEY_SELECTED_IDS] = selected

    if not selected_id:
        st.info("Choose an artifact to preview, or pick one from Browse.")
        return

    entry = index.by_id().get(selected_id)
    if entry is None:
        st.info("Selected artifact is not in the current run index.")
        return
    # Resolve under storage_root for member artifacts
    base = (
        Path(entry.artifact.storage_root)
        if entry.artifact.storage_root
        else ctx.run_root
    )
    render_artifact_file_preview(base, entry.artifact)
    st.caption(f"Size: {entry.size_label} · Role: {entry.artifact_role}")
    try:
        path = ArtifactService.resolve_artifact_source_path(
            ctx.run_root, entry.artifact
        )
        if path and path.exists():
            data = path.read_bytes()
            st.download_button(
                "Download",
                data=data,
                file_name=path.name,
                key=f"artifacts_dl_{selected_id}",
            )
    except Exception as exc:
        st.caption(f"Download unavailable: {exc}")


def _render_export(ctx: RunScopedPageContext) -> None:
    index = build_artifact_index(
        ctx.run_root,
        subject_scope=ctx.subject.subject_type,
        subject_id=ctx.subject.subject_id,
        run_id=ctx.run_id,
    )
    is_group = (ctx.run_root / "group_member_runs.json").exists()
    entries = list(index.entries)
    if is_group:
        source_label = st.selectbox(
            "Export source filter",
            ["All sources", "Group aggregate", "Member sessions"],
            key="artifacts_export_source",
        )
        filt = ArtifactSourceFilter.ALL
        if source_label == "Group aggregate":
            filt = ArtifactSourceFilter.GROUP_AGGREGATE
        elif source_label == "Member sessions":
            filt = ArtifactSourceFilter.MEMBER_SESSIONS
        entries = filter_by_source(entries, filt)
    artifacts = [e.artifact for e in order_artifacts_for_browse(entries)]
    preselected = list(st.session_state.get(ARTIFACTS_KEY_SELECTED_IDS) or [])
    render_export_panel_ui(
        ctx.run_root,
        artifacts,
        key_prefix="artifacts_export",
        preselected_ids=preselected,
    )


def _render_artifacts_body(ctx: RunScopedPageContext) -> None:
    reconcile_artifact_selection(
        st.session_state,
        subject_type=ctx.subject.subject_type,
        subject_id=ctx.subject.subject_id,
        run_id=ctx.run_id,
    )
    # One-shot deep link may force Preview section
    if st.session_state.get(DATA_KEY_ARTIFACT_PRESET) or st.session_state.get(
        "_artifacts_force_preview"
    ):
        _force_preview_section()

    render_page_shell(
        "Artifacts",
        "Browse, preview, and export run outputs.",
        badges=None,
        actions=None,
    )
    section = _section_nav()
    if section == "Browse":
        _render_browse(ctx)
    elif section == "Preview":
        _render_preview(ctx)
    else:
        _render_export(ctx)


def render_artifacts() -> None:
    render_run_scoped_page(_ARTIFACTS_CONFIG, render_body=_render_artifacts_body)
