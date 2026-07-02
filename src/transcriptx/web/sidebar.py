"""Sidebar renderer for TranscriptX app."""

from __future__ import annotations

from collections.abc import Callable

import streamlit as st

from transcriptx.web.navigation import (
    context_readiness,
    evaluate_page_access,
    should_hydrate_workspace_context,
)
from transcriptx.web.services import RunIndex, SubjectService
from transcriptx.web.sidebar_hydration import hydrate_sidebar_state
from transcriptx.web.sidebar_options import get_transcript_dropdown_options
from transcriptx.web.sidebar_state import (
    SidebarSelectionResult,
    apply_sidebar_selection,
    apply_transitional_sidebar_backfill,
    derive_sidebar_state,
)
from transcriptx.web.sidebar_workspace import (
    build_group_labels,
    render_group_picker,
    render_run_picker,
    render_sidebar_stats,
    render_transcript_picker,
)
from transcriptx.web.state import (
    PAGE_KEY,
    RUN_ID_KEY,
    SUBJECT_ID_KEY,
    TX_NAV_EXPANDER_CONFIG,
    TX_NAV_EXPANDER_TOOLS,
    TX_NAV_EXPANDER_VIEW,
    TX_NAV_EXPANDER_WORKFLOW,
    TX_NAV_PENDING_OPEN_VIEW,
    TX_NAV_WORKSPACE_SELECTOR_REQUESTED,
)


def _sidebar_section(
    title: str, state_key: str, render_body: Callable[[], None]
) -> None:
    """Render a collapsible sidebar section driven by explicit session-state toggles."""
    is_open = st.toggle(title, key=state_key)
    if is_open:
        render_body()


def render_sidebar(
    *,
    current_page: str,
    corrections_studio_available: bool,
    prerequisites: dict,
) -> None:
    """Sidebar: global nav, context strip, collapsible groups."""
    # First paint contract: primary navigation must render without hydrating
    # transcript/group/run workspace data.

    def _apply_navigation(page_key: str) -> None:
        st.session_state[PAGE_KEY] = page_key
        st.rerun()

    def _nav_button(
        page_key: str,
        label: str,
        *,
        key_suffix: str = "",
        disabled: bool = False,
        help: str | None = None,
    ) -> None:
        is_active = current_page == page_key and not disabled
        text = f"**{label}**" if is_active else label
        btn_key = f"nav_{page_key}{key_suffix}"
        if disabled:
            st.button(
                text,
                key=btn_key,
                width="stretch",
                type="secondary",
                disabled=True,
                help=help,
            )
            return
        if is_active:
            st.markdown('<div class="nav-active-item">', unsafe_allow_html=True)
        if st.button(text, key=btn_key, width="stretch", type="secondary", help=help):
            _apply_navigation(page_key)
        if is_active:
            st.markdown("</div>", unsafe_allow_html=True)

    def _subject_section(label: str) -> None:
        st.markdown(
            f'<p class="subject-section-header">{label}</p>', unsafe_allow_html=True
        )

    st.markdown("### 🎙️ TranscriptX")
    _nav_button("Home", "Home")
    _nav_button("Library", "Library")
    _nav_button("Search", "Search")
    _nav_button("Statistics", "Statistics")

    readiness = context_readiness(st.session_state)
    overview_access = evaluate_page_access("Overview", prerequisites, readiness)
    if overview_access.allowed:
        if st.button("Open Overview", key="tx_nav_jump_overview", width="stretch"):
            _apply_navigation("Overview")

    sidebar_state = derive_sidebar_state(st.session_state)
    apply_transitional_sidebar_backfill(
        st.session_state,
        prioritize_view=sidebar_state.prioritize_view,
    )
    if st.session_state.pop(TX_NAV_PENDING_OPEN_VIEW, False):
        st.session_state[TX_NAV_EXPANDER_VIEW] = True

    def _render_workflow_section() -> None:
        # tx_sidebar_workflow_nav (order asserted in tests/web/test_upload_transcript_page.py)
        _nav_button("Transcribe Audio", "Transcribe Audio")
        _nav_button("Import Transcript", "Import Transcript")
        _nav_button("Speaker ID", "Speaker Identification")
        _nav_button("Run Analysis", "Run Analysis")
        _nav_button("Batch Ops", "Batch Analysis")
        _nav_button("Groups", "Groups")

    _sidebar_section("Workflow", TX_NAV_EXPANDER_WORKFLOW, _render_workflow_section)

    view_open = st.toggle("View", key=TX_NAV_EXPANDER_VIEW)

    explicit_request = bool(
        st.session_state.get(TX_NAV_WORKSPACE_SELECTOR_REQUESTED, False)
    )
    should_load_workspace = should_hydrate_workspace_context(
        current_page,
        view_opened=view_open,
        explicit_request=explicit_request,
    )

    if should_load_workspace:
        subject_type_label = st.radio(
            "Type",
            ["Transcript", "Group"],
            index=0,
            horizontal=True,
            key="subject_type_selector",
            label_visibility="collapsed",
        )
        subject_type = "transcript" if subject_type_label == "Transcript" else "group"
        current_run_id = st.session_state.get(RUN_ID_KEY)

        if subject_type == "transcript":
            transcript_options, transcript_format = get_transcript_dropdown_options()
            groups: list = []
        else:
            transcript_options = []
            transcript_format = lambda x: x  # noqa: E731
            try:
                from transcriptx.web.cache_helpers import cached_list_groups

                groups = cached_list_groups()
            except Exception:
                groups = []

        pre_subject = SubjectService.resolve_current_subject(st.session_state)
        pre_runs = (
            RunIndex.list_runs(pre_subject.scope, subject_id=pre_subject.subject_id)
            if pre_subject
            else []
        )
        pre_state = hydrate_sidebar_state(
            st.session_state,
            subject_type=subject_type,
            explicit_request=explicit_request,
            transcript_options=transcript_options,
            groups=groups,
            resolved_subject=pre_subject,
            runs=pre_runs,
        )

        if subject_type == "transcript":
            if not transcript_options:
                render_sidebar_stats(status=pre_state.status, subject_type=subject_type)
                apply_sidebar_selection(
                    st.session_state,
                    SidebarSelectionResult(
                        subject_type=subject_type, subject_id=None, run_id=None
                    ),
                )
            else:
                selected = render_transcript_picker(
                    options=transcript_options,
                    format_func=transcript_format,
                    default_subject_id=pre_state.subject_id,
                )
                apply_sidebar_selection(
                    st.session_state,
                    SidebarSelectionResult(
                        subject_type=subject_type,
                        subject_id=selected,
                        run_id=current_run_id,
                    ),
                )
        elif not groups:
            render_sidebar_stats(status=pre_state.status, subject_type=subject_type)
            apply_sidebar_selection(
                st.session_state,
                SidebarSelectionResult(
                    subject_type=subject_type, subject_id=None, run_id=None
                ),
            )
        else:
            group_labels = build_group_labels(groups)
            selected_group = render_group_picker(
                group_keys=pre_state.group_keys or [],
                group_labels=group_labels,
                default_subject_id=pre_state.subject_id,
            )
            apply_sidebar_selection(
                st.session_state,
                SidebarSelectionResult(
                    subject_type=subject_type,
                    subject_id=selected_group,
                    run_id=current_run_id,
                ),
            )

        subject = SubjectService.resolve_current_subject(st.session_state)
        if subject:
            runs = RunIndex.list_runs(subject.scope, subject_id=subject.subject_id)
            run_options = [r.run_id for r in runs]
            post_state = hydrate_sidebar_state(
                st.session_state,
                subject_type=subject_type,
                explicit_request=explicit_request,
                transcript_options=transcript_options,
                groups=groups,
                resolved_subject=subject,
                runs=runs,
            )
            if run_options:
                selected_run_id = render_run_picker(
                    run_options=run_options,
                    default_run_id=post_state.run_id,
                )
                apply_sidebar_selection(
                    st.session_state,
                    SidebarSelectionResult(
                        subject_type=subject_type,
                        subject_id=st.session_state.get(SUBJECT_ID_KEY),
                        run_id=selected_run_id,
                    ),
                )
            else:
                render_sidebar_stats(
                    show_no_selection=True, status="ready", subject_type=subject_type
                )
                apply_sidebar_selection(
                    st.session_state,
                    SidebarSelectionResult(
                        subject_type=subject_type,
                        subject_id=st.session_state.get(SUBJECT_ID_KEY),
                        run_id=None,
                    ),
                )
        else:
            render_sidebar_stats(
                show_no_selection=True, status="ready", subject_type=subject_type
            )
            apply_sidebar_selection(
                st.session_state,
                SidebarSelectionResult(
                    subject_type=subject_type,
                    subject_id=st.session_state.get(SUBJECT_ID_KEY),
                    run_id=None,
                ),
            )
    elif not view_open:
        st.caption("Open View to load transcript and run selectors")
        if st.button(
            "Open View to load selectors",
            key="tx_nav_open_view_selectors",
            width="stretch",
        ):
            st.session_state[TX_NAV_PENDING_OPEN_VIEW] = True
            st.rerun()

    if view_open:
        _subject_section("Pages")
        view_page_sections = (
            ("Read", (("Transcript", "Transcript"),)),
            (
                "Summarise",
                (
                    ("Overview", "Overview"),
                    ("Insights", "Insights"),
                ),
            ),
            (
                "Explore",
                (
                    ("Charts", "Charts"),
                    ("Data", "Data"),
                    ("Explorer", "File List"),
                ),
            ),
        )
        for section_title, pages in view_page_sections:
            _subject_section(section_title)
            for key, label in pages:
                access = evaluate_page_access(key, prerequisites, readiness)
                _nav_button(
                    key,
                    label,
                    key_suffix="_subject",
                    disabled=not access.allowed,
                    help=access.help_text,
                )

    # tx_sidebar_tools_group (test anchor: workflow nav must appear above this)
    def _render_tools_section() -> None:
        if corrections_studio_available:
            _nav_button("Corrections Studio", "Corrections Studio")
        _nav_button("Audio Prep", "Audio Pre-processing")
        _nav_button("Audio Merge", "Audio Merge")
        _nav_button("Dashboard Builder", "Dashboard Builder")

    _sidebar_section("Tools", TX_NAV_EXPANDER_TOOLS, _render_tools_section)

    def _render_settings_section() -> None:
        _nav_button("Settings", "Settings")
        _nav_button("Profiles", "Profiles")
        _nav_button("Diagnostics", "Diagnostics")

    _sidebar_section("Settings", TX_NAV_EXPANDER_CONFIG, _render_settings_section)
