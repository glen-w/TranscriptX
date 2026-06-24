"""Transcript page module.

Search/timestamp controls and segment tabs run in ``@st.fragment`` so toggling them
does not reload the full transcript and sidebar.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import streamlit as st

from transcriptx.web.components.empty_state import render_empty_state
from transcriptx.web.components.page_shell import render_page_help, render_page_shell
from transcriptx.web.page_modules.insights import (
    _render_highlights_section,
    _render_summary_section,
)
from transcriptx.web.services import FileService, RunIndex, SubjectService
from transcriptx.web.utils import list_available_sessions
from transcriptx.web.transcript_view_state import (
    consume_nav_request,
    filtered_display_segments,
    resolve_transcript_artifacts,
)
from transcriptx.web.transcript_viewer.downloads import render_download_row
from transcriptx.web.transcript_viewer.metadata import (
    segment_word_stats,
    speaker_tooltip,
)
from transcriptx.web.transcript_viewer.modules_panel import render_modules_panel
from transcriptx.web.transcript_viewer.preflight import (
    ViewerPreflight,
    resolve_viewer_preflight,
)
from transcriptx.web.transcript_viewer.segments import (
    render_plain_segments,
    render_segmented_tab,
)
from transcriptx.web.utils import (
    load_transcript_by_session,
    resolve_speaker_names_from_db,
)
from transcriptx.web.state import (
    NAV_REQUEST_KEY,
    PAGE_KEY,
    RUN_ID_KEY,
    SUBJECT_ID_KEY,
    SUBJECT_TYPE_KEY,
)

from transcriptx.core.utils.logger import get_logger
from transcriptx.web.models.search import NavRequest, SegmentRef

logger = get_logger()


@dataclass(frozen=True)
class TranscriptControlsState:
    search_text: str
    show_timestamps: bool
    format_key: str


def navigate_to_segment(
    segment_ref: SegmentRef, highlight_query: str | None = None
) -> None:
    """Jump from search results into Transcript page context and rerun."""
    st.session_state[SUBJECT_TYPE_KEY] = "transcript"
    st.session_state[SUBJECT_ID_KEY] = segment_ref.transcript_ref.session_slug
    st.session_state[RUN_ID_KEY] = segment_ref.transcript_ref.run_id
    st.session_state[PAGE_KEY] = "Transcript"
    st.session_state[NAV_REQUEST_KEY] = NavRequest(
        segment_ref=segment_ref,
        highlight_query=highlight_query,
    )
    st.rerun()


def _render_group_browser(subject) -> None:
    """Render group member selector and switch context to transcript on click."""
    st.subheader("Group transcripts")
    if not subject.members:
        st.info("This group has no transcripts.")
        return
    st.caption("Select a transcript to open its viewer.")
    sessions = list_available_sessions()
    for index, member in enumerate(subject.members, start=1):
        display_name = (
            member.file_name
            or (Path(member.file_path).name if member.file_path else None)
            or "(unknown)"
        )
        numbered_name = f"{index}. {display_name}"
        session_info = FileService.resolve_session_for_transcript_path(
            member.file_path, sessions
        )
        if session_info:
            session_slug, session_run_id = session_info
            member_key = member.uuid or f"index_{index}"
            if st.button(
                f"View: {numbered_name}",
                key=f"group_member_transcript_{member_key}",
            ):
                st.session_state[SUBJECT_TYPE_KEY] = "transcript"
                st.session_state[SUBJECT_ID_KEY] = session_slug
                st.session_state[RUN_ID_KEY] = session_run_id
                st.session_state[PAGE_KEY] = "Transcript"
                st.rerun()
        else:
            st.caption(f"{numbered_name} (session not found)")


def _render_preflight_empty_state(preflight: ViewerPreflight) -> None:
    """Render preflight empty states without mutating navigation context."""
    if preflight.status == "no_subject":
        render_empty_state(
            "missing_prerequisite",
            "No subject selected",
            "Choose a transcript or group in the sidebar, then pick a run.",
            primary_action=("Open Library", "Library"),
            secondary_action=("Run Analysis", "Run Analysis"),
        )
    elif preflight.status == "wrong_subject":
        render_empty_state(
            "missing_prerequisite",
            "Transcript view needs a transcript subject",
            "Switch the sidebar context to **Transcript** or open a member from **Groups**.",
            primary_action=("Groups", "Groups"),
            secondary_action=("Overview", "Overview"),
        )
    elif preflight.status == "no_run":
        render_empty_state(
            "missing_prerequisite",
            "No run selected",
            "Select a run for this transcript in the sidebar.",
            primary_action=("Run Analysis", "Run Analysis"),
            secondary_action=("Overview", "Overview"),
        )
    else:
        render_empty_state(
            "missing_prerequisite",
            "Transcript context unavailable",
            "Select a transcript and run in the sidebar.",
            primary_action=("Overview", "Overview"),
            secondary_action=("Library", "Library"),
        )


def _render_metadata_metrics(transcript_data: dict) -> None:
    """Render top-level transcript metadata metrics."""
    metadata = transcript_data.get("metadata", {})
    segments = transcript_data.get("segments", []) or []
    speaker_help = speaker_tooltip(segments)
    seg_count, total_words, avg_words = segment_word_stats(segments)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Duration", f"{metadata.get('duration_seconds', 0) / 60:.1f} min")
    with col2:
        st.metric("Speakers", metadata.get("speaker_count", 0), help=speaker_help)
    with col3:
        st.metric(
            "Segments",
            seg_count,
            help=f"Total words: {total_words:,}\nAverage words/segment: {avg_words:.1f}",
        )
    with col4:
        st.metric("Language", metadata.get("language", "Unknown"))


def _render_transcript_help(help_markdown: str) -> None:
    """Render transcript page help/footer content."""
    render_page_help(help_markdown)


def _render_transcript_controls() -> TranscriptControlsState:
    """Render search and timestamp controls with existing widget keys."""
    st.markdown('<div class="tx-transcript-controls">', unsafe_allow_html=True)
    search_text = st.text_input("🔍 Search in transcript", key="transcript_search")
    show_timestamps = st.checkbox("Show timestamps", key="show_timestamps")
    format_key = st.session_state.get("timestamp_format", "seconds")
    st.markdown("</div>", unsafe_allow_html=True)
    return TranscriptControlsState(
        search_text=search_text,
        show_timestamps=show_timestamps,
        format_key=format_key,
    )


def _resolve_and_prepare_segments(
    transcript_data: dict[str, Any], selected_session: str
) -> list[dict[str, Any]]:
    """Resolve speaker names for transcript segments and return segment list."""
    segments = transcript_data.get("segments", [])
    if segments:
        segments = resolve_speaker_names_from_db(segments, selected_session)
    return segments


def _render_transcript_tabs(
    display_segments: list[tuple[int, dict[str, Any]]],
    *,
    controls: TranscriptControlsState,
    highlight_query: str | None,
    jump_index: int | None,
) -> None:
    """Render plain/segmented tabs for already-filtered display segments."""
    tab_plain, tab_segmented = st.tabs(["Plain", "Segmented"])
    with tab_plain:
        render_plain_segments(
            display_segments,
            show_timestamps=controls.show_timestamps,
            format_key=controls.format_key,
            highlight_query=highlight_query,
            jump_index=jump_index,
        )
    with tab_segmented:
        render_segmented_tab(
            display_segments,
            show_timestamps=controls.show_timestamps,
            format_key=controls.format_key,
        )


def _render_transcript_outputs(selected_session: str, run_root: Path) -> None:
    """Render analysis outputs and insight expanders for a transcript run."""
    render_modules_panel(selected_session)
    st.divider()
    with st.expander("✨ Highlights", expanded=False):
        _render_highlights_section(run_root)
    with st.expander("🧾 Executive Summary", expanded=False):
        _render_summary_section(run_root)


@st.fragment
def _transcript_interaction_fragment(
    segments: list[dict[str, Any]],
    selected_session: str,
    run_root: Path,
    *,
    highlight_query: str | None,
    jump_index: int | None,
) -> None:
    """Transcript search, tabs, and outputs without full-app rerun."""
    controls = _render_transcript_controls()

    display_segments, filter_caption = filtered_display_segments(
        segments=segments,
        search_text=controls.search_text,
        jump_index=jump_index,
    )
    if filter_caption:
        st.caption(filter_caption)

    _render_transcript_tabs(
        display_segments,
        controls=controls,
        highlight_query=highlight_query,
        jump_index=jump_index,
    )
    _render_transcript_outputs(selected_session, run_root)


def render_transcript_viewer() -> None:
    """Transcript viewer page."""
    transcript_help = (
        "**What this shows:** Segments for the selected transcript run.\n\n"
        "**Search** filters the list. Use **Plain** for line-by-line reading or "
        "**Segmented** for speaker blocks."
    )

    render_page_shell(
        "Transcript",
        "Read the diarized transcript for the current run, search segments, and open highlights.",
        badges=None,
        actions=None,
    )
    st.session_state.setdefault("show_timestamps", True)
    st.session_state.setdefault("timestamp_format", "seconds")
    if st.session_state.get("timestamp_format") == "real_time":
        st.session_state["timestamp_format"] = "seconds"
    try:
        preflight = resolve_viewer_preflight(
            st.session_state,
            resolve_subject=SubjectService.resolve_current_subject,
            get_run_root=lambda scope, run_id, subject_id: RunIndex.get_run_root(
                scope, run_id, subject_id=subject_id
            ),
        )
        if preflight.status == "group_browser":
            _render_group_browser(preflight.subject)
            _render_transcript_help(transcript_help)
            return
        if preflight.status != "ok":
            _render_preflight_empty_state(preflight)
            _render_transcript_help(transcript_help)
            return
        context = preflight.context_result
        selected = context.selected_session if context else None
        run_root = context.run_root if context else None
        run_id = context.run_id if context else None
        session_slug = context.session_slug if context else None
        if not selected or not run_root or not run_id or not session_slug:
            _render_preflight_empty_state(
                ViewerPreflight(status="context_failed", context_result=context)
            )
            _render_transcript_help(transcript_help)
            return

        with st.spinner(f"Loading transcript for {selected}..."):
            transcript_data = load_transcript_by_session(selected)
        if not transcript_data:
            st.error(f"Transcript not found for session: {selected}")
            _render_transcript_help(transcript_help)
            return

        _render_metadata_metrics(transcript_data)
        artifacts = resolve_transcript_artifacts(
            run_root=run_root,
            selected_session=session_slug,
            run_id=run_id,
        )
        render_download_row(artifacts, transcript_data, selected)
        st.divider()

        segments = _resolve_and_prepare_segments(transcript_data, selected)
        if not segments:
            render_empty_state(
                "no_results_yet",
                "No segments in this transcript",
                "The transcript file may be empty or in an unexpected format.",
                primary_action=("Open Library", "Library"),
                secondary_action=None,
            )
            _render_transcript_help(transcript_help)
            return

        # Preserve existing behavior: nav_request is consumed only once transcript
        # segments are successfully resolved and render path can continue.
        nav_state = consume_nav_request(st.session_state)
        if nav_state.clear_nav_request:
            st.session_state[NAV_REQUEST_KEY] = None

        _transcript_interaction_fragment(
            segments,
            selected,
            run_root,
            highlight_query=nav_state.highlight_query,
            jump_index=nav_state.jump_index,
        )
        _render_transcript_help(transcript_help)
    except Exception as exc:
        logger.error(f"Error loading transcript: {exc}", exc_info=True)
        st.error(f"Error loading transcript: {exc}")
        st.exception(exc)
        _render_transcript_help(transcript_help)
