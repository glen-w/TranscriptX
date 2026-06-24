"""Sidebar renderer for TranscriptX app."""

from __future__ import annotations

import streamlit as st

from transcriptx.web.navigation import context_readiness, evaluate_page_access
from transcriptx.web.services import RunIndex, SubjectService
from transcriptx.web.sidebar_options import get_transcript_dropdown_options
from transcriptx.web.sidebar_state import (
    SidebarSelectionResult,
    apply_sidebar_selection,
    apply_transitional_sidebar_backfill,
    derive_sidebar_state,
)
from transcriptx.web.state import (
    PAGE_KEY,
    RUN_ID_KEY,
    SELECTBOX_PLACEHOLDER_GROUP,
    SELECTBOX_PLACEHOLDER_TRANSCRIPT,
    SUBJECT_ID_KEY,
    TX_NAV_EXPANDER_CONFIG,
    TX_NAV_EXPANDER_TOOLS,
    TX_NAV_EXPANDER_VIEW,
    TX_NAV_EXPANDER_WORKFLOW,
)


def render_sidebar(
    *,
    current_page: str,
    corrections_studio_available: bool,
    prerequisites: dict,
) -> None:
    """Sidebar: global nav, context strip, collapsible groups."""

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

    with st.expander(  # type: ignore[call-arg]
        "Workflow",
        expanded=st.session_state[TX_NAV_EXPANDER_WORKFLOW],
        key=TX_NAV_EXPANDER_WORKFLOW,
        on_change="rerun",
    ):
        # tx_sidebar_workflow_nav (order asserted in tests/web/test_upload_transcript_page.py)
        _nav_button("Transcribe Audio", "Transcribe Audio")
        _nav_button("Import Transcript", "Import Transcript")
        _nav_button("Speaker ID", "Speaker Identification")
        _nav_button("Run Analysis", "Run Analysis")
        _nav_button("Batch Ops", "Batch Analysis")
        _nav_button("Groups", "Groups")

    with st.expander(  # type: ignore[call-arg]
        "View",
        expanded=st.session_state[TX_NAV_EXPANDER_VIEW],
        key=TX_NAV_EXPANDER_VIEW,
        on_change="rerun",
    ):
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
            if not transcript_options:
                st.caption("No transcripts yet")
                apply_sidebar_selection(
                    st.session_state,
                    SidebarSelectionResult(
                        subject_type=subject_type, subject_id=None, run_id=None
                    ),
                )
            else:
                current = st.session_state.get("subject_id")
                default_idx = 0
                if current and current in transcript_options:
                    default_idx = transcript_options.index(current) + 1
                selected = st.selectbox(
                    "Transcript",
                    [""] + transcript_options,
                    format_func=lambda x: (
                        SELECTBOX_PLACEHOLDER_TRANSCRIPT
                        if x == ""
                        else transcript_format(x)
                    ),
                    index=default_idx,
                    key="subject_id_selector",
                )
                apply_sidebar_selection(
                    st.session_state,
                    SidebarSelectionResult(
                        subject_type=subject_type,
                        subject_id=selected if selected else None,
                        run_id=current_run_id,
                    ),
                )
        else:
            try:
                from transcriptx.web.cache_helpers import cached_list_groups

                groups = cached_list_groups()
            except Exception:
                groups = []
            if not groups:
                st.caption("No groups yet")
                apply_sidebar_selection(
                    st.session_state,
                    SidebarSelectionResult(
                        subject_type=subject_type, subject_id=None, run_id=None
                    ),
                )
            else:
                group_labels = {
                    g.uuid: f"{g.name or 'Unnamed'} • {len(g.transcript_file_uuids or [])} transcripts"
                    for g in groups
                }
                group_keys = [g.uuid for g in groups]
                current = st.session_state.get("subject_id")
                default_idx = 0
                if current and current in group_keys:
                    default_idx = group_keys.index(current) + 1
                selected_group = st.selectbox(
                    "Group",
                    [""] + group_keys,
                    format_func=lambda key: (
                        SELECTBOX_PLACEHOLDER_GROUP
                        if key == ""
                        else group_labels.get(key, key)
                    ),
                    index=default_idx,
                    key="subject_id_selector",
                )
                apply_sidebar_selection(
                    st.session_state,
                    SidebarSelectionResult(
                        subject_type=subject_type,
                        subject_id=selected_group if selected_group else None,
                        run_id=current_run_id,
                    ),
                )

        subject = SubjectService.resolve_current_subject(st.session_state)
        if subject:
            runs = RunIndex.list_runs(subject.scope, subject_id=subject.subject_id)
            run_options = [r.run_id for r in runs]
            if run_options:
                current_run = st.session_state.get("run_id")
                index = (
                    run_options.index(current_run) if current_run in run_options else 0
                )
                selected_run_id = st.selectbox(
                    "Run",
                    run_options,
                    index=index,
                    key="run_selector",
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
                st.caption("No runs yet")
                apply_sidebar_selection(
                    st.session_state,
                    SidebarSelectionResult(
                        subject_type=subject_type,
                        subject_id=st.session_state.get(SUBJECT_ID_KEY),
                        run_id=None,
                    ),
                )
        else:
            apply_sidebar_selection(
                st.session_state,
                SidebarSelectionResult(
                    subject_type=subject_type,
                    subject_id=st.session_state.get(SUBJECT_ID_KEY),
                    run_id=None,
                ),
            )

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
    with st.expander(  # type: ignore[call-arg]
        "Tools",
        expanded=st.session_state[TX_NAV_EXPANDER_TOOLS],
        key=TX_NAV_EXPANDER_TOOLS,
        on_change="rerun",
    ):
        if corrections_studio_available:
            _nav_button("Corrections Studio", "Corrections Studio")
        _nav_button("Audio Prep", "Audio Pre-processing")
        _nav_button("Audio Merge", "Audio Merge")
        _nav_button("Dashboard Builder", "Dashboard Builder")

    with st.expander(  # type: ignore[call-arg]
        "Settings",
        expanded=st.session_state[TX_NAV_EXPANDER_CONFIG],
        key=TX_NAV_EXPANDER_CONFIG,
        on_change="rerun",
    ):
        _nav_button("Settings", "Settings")
        _nav_button("Profiles", "Profiles")
        _nav_button("Diagnostics", "Diagnostics")
