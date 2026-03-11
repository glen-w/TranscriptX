"""
Streamlit-based web interface for TranscriptX.

This replaces the Flask/Jinja2 web interface with a simpler, more maintainable
Streamlit implementation.

To run:
    streamlit run src/transcriptx/web/app.py
"""

import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

# Import existing utilities
try:
    from transcriptx.web.utils import (
        list_available_sessions,
        load_transcript_by_session,
        get_analysis_modules,
        load_analysis_data,
        get_all_sessions_statistics,
        extract_analysis_summary,
    )
    from transcriptx.web.db_utils import (
        get_all_speakers,
        get_speaker_by_id,
        get_speaker_statistics,
        get_speaker_conversations,
        get_speaker_profiles,
        format_speaker_profile_data,
    )
    from transcriptx.web.services import (
        FileService,
        ArtifactService,
        RunIndex,
        SubjectService,
    )
    from transcriptx.web.page_modules.overview import render_overview
    from transcriptx.web.page_modules.home import render_home
    from transcriptx.web.page_modules.library import render_library
    from transcriptx.web.page_modules.run_analysis import render_run_analysis_page
    from transcriptx.web.page_modules.settings import render_settings_page
    from transcriptx.web.page_modules.profiles import render_profiles_page
    from transcriptx.web.page_modules.speaker_id import render_speaker_id_page
    from transcriptx.web.page_modules.audio_prep import render_audio_prep_page
    from transcriptx.web.page_modules.audio_merge import render_audio_merge_page
    from transcriptx.web.page_modules.batch_ops import render_batch_ops_page
    from transcriptx.web.page_modules.diagnostics import render_diagnostics_page
    from transcriptx.web.page_modules.charts import render_charts
    from transcriptx.web.page_modules.data import render_data
    from transcriptx.web.page_modules.explorer import render_explorer
    from transcriptx.web.page_modules.groups import render_groups
    from transcriptx.web.page_modules.statistics import render_statistics
    from transcriptx.web.page_modules.search import render_search

    try:
        from transcriptx.web.page_modules.speaker_studio import (
            render_speaker_studio,
            is_speaker_studio_enabled,
        )

        _speaker_studio_available = is_speaker_studio_enabled()
    except ImportError:
        _speaker_studio_available = False
        render_speaker_studio = None  # type: ignore[misc, assignment]

    try:
        from transcriptx.web.page_modules.corrections_studio import (
            render_corrections_studio,
            is_corrections_studio_enabled,
        )

        _corrections_studio_available = is_corrections_studio_enabled()
    except ImportError:
        _corrections_studio_available = False
        render_corrections_studio = None  # type: ignore[misc, assignment]
    from transcriptx.web.page_modules.insights import (
        render_insights,
        _render_highlights_section,
        _render_summary_section,
    )
    from transcriptx.web.models.search import NavRequest, SegmentRef
    from transcriptx.web.pages.configuration import render_configuration_page
    from transcriptx.web.components.exemplars import render_speaker_exemplars
    from transcriptx.web.components.subject_header import render_subject_header
    from transcriptx.core.utils.paths import OUTPUTS_DIR, DIARISED_TRANSCRIPTS_DIR
    from transcriptx.core.utils.logger import get_logger
    from transcriptx.utils.text_utils import format_time_detailed
    from transcriptx.web.module_registry import build_module_label
except ImportError as e:
    st.error(f"Import error: {e}")
    st.stop()

logger = get_logger()

# Page configuration
st.set_page_config(
    page_title="TranscriptX",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better styling
st.markdown(
    """
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .stat-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
    }
    .speaker-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 1rem;
        font-size: 0.875rem;
        font-weight: 500;
        margin-right: 0.5rem;
    }
    /* Navigation section headers */
    .nav-section-header {
        font-size: 0.65rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #8a9ab0;
        margin: 1.1rem 0 0.25rem 0.1rem;
        padding: 0;
        line-height: 1.2;
        user-select: none;
    }
    /* Style navigation buttons to look like sidebar links */
    div[data-testid="stButton"] > button[kind="secondary"] {
        background: transparent;
        border: none;
        border-radius: 6px;
        color: #3d5166;
        text-align: left;
        padding: 0.35rem 0.6rem;
        font-weight: normal;
        font-size: 0.92rem;
        box-shadow: none;
        width: 100%;
        transition: background 0.12s ease, color 0.12s ease;
    }
    div[data-testid="stButton"] > button[kind="secondary"]:hover {
        color: #1f77b4;
        background: #eef4fb;
        text-decoration: none;
    }
    div[data-testid="stButton"] > button[kind="secondary"]:focus {
        box-shadow: none;
        outline: none;
    }
    /* Active nav item — left-bar highlight */
    div[data-testid="stButton"] > button[kind="secondary"].nav-active,
    .nav-active-item > div[data-testid="stButton"] > button[kind="secondary"] {
        background: #ddeeff;
        color: #1f77b4;
        font-weight: 600;
    }
    /* Subject panel section headers (CONTEXT / VIEWS / FILES / ADVANCED) */
    .subject-section-header {
        font-size: 0.65rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #8a9ab0;
        margin: 1rem 0 0.2rem 0.1rem;
        line-height: 1.2;
        user-select: none;
    }
    /* Scroll to top button */
    #scroll-to-top-btn {
        position: fixed;
        bottom: 30px;
        right: 30px;
        width: 50px;
        height: 50px;
        background-color: #1f77b4;
        color: white;
        border: none;
        border-radius: 50%;
        font-size: 24px;
        cursor: pointer;
        display: none;
        z-index: 1000;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        transition: all 0.3s ease;
    }
    #scroll-to-top-btn:hover {
        background-color: #0d5a8a;
        transform: translateY(-2px);
        box-shadow: 0 6px 8px rgba(0, 0, 0, 0.15);
    }
    #scroll-to-top-btn.show {
        display: block;
    }
</style>
<script>
    // Scroll to top button functionality
    window.addEventListener('DOMContentLoaded', function() {
        // Create the button
        const btn = document.createElement('button');
        btn.id = 'scroll-to-top-btn';
        btn.innerHTML = '↑';
        btn.title = 'Return to top';
        btn.onclick = function() {
            window.scrollTo({top: 0, behavior: 'smooth'});
        };
        document.body.appendChild(btn);
        
        // Show/hide button based on scroll position
        window.addEventListener('scroll', function() {
            if (window.pageYOffset > 300) {
                btn.classList.add('show');
            } else {
                btn.classList.remove('show');
            }
        });
    });
</script>
""",
    unsafe_allow_html=True,
)


def _build_session_index_from_list(sessions: list) -> dict:
    """Build slug -> [sessions] map from session list (no I/O)."""
    session_map = {}
    for session in sessions:
        name = session.get("name", "")
        if "/" not in name:
            continue
        slug, run_id = name.split("/", 1)
        session_map.setdefault(slug, [])
        session = {**session, "run_id": run_id}
        session_map[slug].append(session)
    return session_map


def _build_session_index():
    sessions = list_available_sessions()
    return _build_session_index_from_list(sessions)


@st.cache_data(ttl=60, show_spinner=False)
def _get_cached_session_data():
    """Return (session_map, sessions_list) so the app does not recompute on every rerun."""
    sessions_list = list_available_sessions()
    session_map = _build_session_index_from_list(sessions_list)
    return session_map, sessions_list


def _format_timestamp_range(
    start: float, end: float, format_key: str, file_mtime: Optional[float]
) -> str:
    if format_key == "seconds":
        return f"{start:.1f}s - {end:.1f}s"
    if format_key == "real_time":
        if file_mtime is not None:
            recording_start = datetime.fromtimestamp(file_mtime)
            start_dt = recording_start + timedelta(seconds=start)
            end_dt = recording_start + timedelta(seconds=end)
            return f"{start_dt:%Y-%m-%d %H:%M:%S} - {end_dt:%H:%M:%S}"
        format_key = "time"
    return f"{format_time_detailed(start)} - {format_time_detailed(end)}"


def navigate_to_segment(
    segment_ref: SegmentRef, highlight_query: Optional[str] = None
) -> None:
    st.session_state["subject_type"] = "transcript"
    st.session_state["subject_id"] = segment_ref.transcript_ref.session_slug
    st.session_state["run_id"] = segment_ref.transcript_ref.run_id
    st.session_state["page"] = "Transcript"
    st.session_state["nav_request"] = NavRequest(
        segment_ref=segment_ref,
        highlight_query=highlight_query,
    )
    st.rerun()


def render_transcript_viewer():
    """Transcript viewer page."""
    st.markdown(
        '<div class="main-header">📝 Transcript Viewer</div>', unsafe_allow_html=True
    )

    st.session_state.setdefault("show_timestamps", True)
    st.session_state.setdefault("timestamp_format", "seconds")

    try:
        subject = SubjectService.resolve_current_subject(st.session_state)
        run_id = st.session_state.get("run_id")
        if not subject:
            st.info("Select a subject and run to view the transcript.")
            return
        if subject.subject_type == "group":
            st.subheader("Group transcripts")
            if not subject.members:
                st.info("This group has no transcripts.")
                return
            st.caption("Select a transcript to open its viewer.")
            sessions = FileService.list_available_sessions()
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
                        st.session_state["subject_type"] = "transcript"
                        st.session_state["subject_id"] = session_slug
                        st.session_state["run_id"] = session_run_id
                        st.session_state["page"] = "Transcript"
                        st.rerun()
                else:
                    st.caption(f"{numbered_name} (session not found)")
            return
        if subject.subject_type != "transcript":
            st.info("Transcript view is available for transcript subjects only.")
            return
        if not run_id:
            st.info("Select a subject and run to view the transcript.")
            return
        selected_session = subject.subject_id
        selected_run_id = run_id
        selected = f"{selected_session}/{selected_run_id}"
        run_root = RunIndex.get_run_root(
            subject.scope,
            run_id,
            subject_id=subject.subject_id,
        )

        # Load transcript
        with st.spinner(f"Loading transcript for {selected}..."):
            transcript_data = load_transcript_by_session(selected)

        if not transcript_data:
            st.error(f"Transcript not found for session: {selected}")
            return

        # Display metadata
        if "metadata" in transcript_data:
            metadata = transcript_data["metadata"]
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric(
                    "Duration", f"{metadata.get('duration_seconds', 0) / 60:.1f} min"
                )
            with col2:
                st.metric("Speakers", metadata.get("speaker_count", 0))
            with col3:
                st.metric("Segments", len(transcript_data.get("segments", [])))
            with col4:
                st.metric("Language", metadata.get("language", "Unknown"))

        # Download buttons - check for files in output folder
        st.subheader("📥 Download Transcript")
        download_cols = st.columns(3)

        # Find transcript files in output folder
        session_output_dir = run_root
        transcripts_dir = session_output_dir / "transcripts"
        manifest_path = session_output_dir / ".transcriptx" / "manifest.json"
        manifest_transcript_path = None
        base_name = None
        if manifest_path.exists():
            try:
                from transcriptx.core.pipeline.manifest_loader import load_run_manifest

                manifest = load_run_manifest(manifest_path)
                manifest_transcript_path = manifest.get("transcript_path")
                if manifest_transcript_path:
                    base_name = Path(manifest_transcript_path).stem
            except Exception as e:
                logger.warning(f"Failed to read manifest for {selected}: {e}")

        if base_name is None:
            base_name = selected.split("/", 1)[-1]

        # JSON file
        json_file = None
        json_paths = []
        if manifest_transcript_path:
            json_paths.append(Path(manifest_transcript_path))
        json_paths.extend(
            [
                Path(DIARISED_TRANSCRIPTS_DIR) / f"{base_name}.json",
                Path(DIARISED_TRANSCRIPTS_DIR)
                / f"{base_name}_transcript_diarised.json",
            ]
        )
        for path in json_paths:
            if path.exists():
                json_file = path
                break

        # TXT and CSV files
        txt_file = None
        csv_file = None
        if transcripts_dir.exists():
            txt_files = list(transcripts_dir.glob(f"{base_name}-transcript.txt"))
            csv_files = list(transcripts_dir.glob(f"{base_name}-transcript.csv"))
            if txt_files:
                txt_file = txt_files[0]
            if csv_files:
                csv_file = csv_files[0]

        with download_cols[0]:
            if json_file and json_file.exists():
                with open(json_file, "rb") as f:
                    st.download_button(
                        label="📥 Download JSON",
                        data=f.read(),
                        file_name=json_file.name,
                        mime="application/json",
                        key="download_json",
                    )
            else:
                # Fallback: generate JSON from current data
                transcript_json = json.dumps(transcript_data, indent=2, default=str)
                st.download_button(
                    label="📥 Download JSON",
                    data=transcript_json,
                    file_name=f"{selected}_transcript.json",
                    mime="application/json",
                    key="download_json",
                )

        with download_cols[1]:
            if txt_file and txt_file.exists():
                with open(txt_file, "rb") as f:
                    st.download_button(
                        label="📥 Download TXT",
                        data=f.read(),
                        file_name=txt_file.name,
                        mime="text/plain",
                        key="download_txt",
                    )
            else:
                st.info("TXT not available")

        with download_cols[2]:
            if csv_file and csv_file.exists():
                with open(csv_file, "rb") as f:
                    st.download_button(
                        label="📥 Download CSV",
                        data=f.read(),
                        file_name=csv_file.name,
                        mime="text/csv",
                        key="download_csv",
                    )
            else:
                st.info("CSV not available")

        st.divider()

        # Resolve speaker names from database
        from transcriptx.web.utils import resolve_speaker_names_from_db

        segments = transcript_data.get("segments", [])
        if segments:
            segments = resolve_speaker_names_from_db(segments, selected)

        source_metadata = transcript_data.get("source", {})
        if not isinstance(source_metadata, dict):
            source_metadata = {}
        file_mtime = source_metadata.get("file_mtime")
        if not isinstance(file_mtime, (int, float)):
            file_mtime = None

        nav_request = st.session_state.get("nav_request")
        highlight_query = None
        jump_index = None
        if nav_request:
            highlight_query = nav_request.highlight_query
            segment_ref = nav_request.segment_ref
            if segment_ref.primary_locator == "db_id" and segment_ref.segment_id:
                try:
                    from transcriptx.database import get_session
                    from transcriptx.database.models import TranscriptSegment

                    session = get_session()
                    try:
                        segment = (
                            session.query(TranscriptSegment)
                            .filter(TranscriptSegment.id == segment_ref.segment_id)
                            .first()
                        )
                    finally:
                        session.close()
                    if segment and segment.segment_index is not None:
                        jump_index = segment.segment_index
                except Exception as e:
                    logger.warning(f"Failed to resolve segment by DB id: {e}")
            elif segment_ref.segment_index is not None:
                jump_index = segment_ref.segment_index
            st.session_state["nav_request"] = None

        if not segments:
            st.info("No segments found in transcript")
            return

        st.subheader(f"Transcript Segments ({len(segments)} total)")

        # Search in transcript
        search_text = st.text_input("🔍 Search in transcript", key="transcript_search")

        controls_col, format_col = st.columns(2)
        with controls_col:
            show_timestamps = st.checkbox(
                "Show timestamps",
                key="show_timestamps",
            )
        with format_col:
            format_options = ["seconds", "time", "real_time"]
            format_key = st.selectbox(
                "Timestamp format",
                format_options,
                format_func=lambda value: {
                    "seconds": "Seconds",
                    "time": "Time",
                    "real_time": "Real Time",
                }.get(value, value),
                key="timestamp_format",
                disabled=not show_timestamps,
            )

        # Filter segments
        display_segments: List[tuple[int, dict]] = list(enumerate(segments))
        if search_text:
            display_segments = [
                (idx, s)
                for idx, s in display_segments
                if search_text.lower() in s.get("text", "").lower()
            ]
            st.caption(f"Showing {len(display_segments)} of {len(segments)} segments")
        elif jump_index is not None:
            start_idx = max(0, jump_index - 2)
            end_idx = min(len(segments) - 1, jump_index + 2)
            display_segments = [
                (idx, segments[idx]) for idx in range(start_idx, end_idx + 1)
            ]
            st.caption("Showing context around selected segment.")

        tab_plain, tab_segmented = st.tabs(["Plain", "Segmented"])

        with tab_plain:
            for segment_index, segment in display_segments:
                speaker = segment.get("speaker_display") or segment.get(
                    "speaker", "Unknown"
                )
                text = segment.get("text", "")
                start = segment.get("start", 0)
                end = segment.get("end", 0)
                rendered_text = text
                if highlight_query and segment_index == jump_index:
                    spans = []
                    lower_text = text.lower()
                    lower_query = highlight_query.lower()
                    pos = 0
                    while True:
                        idx = lower_text.find(lower_query, pos)
                        if idx == -1:
                            break
                        spans.append((idx, idx + len(lower_query)))
                        pos = idx + len(lower_query)
                    if spans:
                        import html

                        rendered_parts = []
                        cursor = 0
                        for span_start, span_end in spans:
                            rendered_parts.append(html.escape(text[cursor:span_start]))
                            rendered_parts.append(
                                f"<mark>{html.escape(text[span_start:span_end])}</mark>"
                            )
                            cursor = span_end
                        rendered_parts.append(html.escape(text[cursor:]))
                        rendered_text = "".join(rendered_parts)
                if show_timestamps:
                    timestamp = _format_timestamp_range(
                        start, end, format_key, file_mtime
                    )
                    st.markdown(f"**{speaker}** · ⏱️ {timestamp}")
                else:
                    st.markdown(f"**{speaker}**")
                if rendered_text != text:
                    st.markdown(rendered_text, unsafe_allow_html=True)
                else:
                    st.write(text)
                st.divider()

        with tab_segmented:
            speaker_groups = []
            current_speaker = None
            current_group = []

            for _, segment in display_segments:
                speaker = segment.get("speaker_display") or segment.get(
                    "speaker", "Unknown"
                )
                if speaker != current_speaker:
                    if current_group:
                        speaker_groups.append((current_speaker, current_group))
                    current_speaker = speaker
                    current_group = [segment]
                else:
                    current_group.append(segment)
            if current_group:
                speaker_groups.append((current_speaker, current_group))

            for speaker_name, group_segments in speaker_groups:
                # Calculate group timestamp range (from first segment start to last segment end)
                group_start = group_segments[0].get("start", 0)
                group_end = group_segments[-1].get("end", 0)

                # Build expander title with timestamp if enabled
                if show_timestamps:
                    group_timestamp = _format_timestamp_range(
                        group_start, group_end, format_key, file_mtime
                    )
                    expander_title = f"🎤 {speaker_name} ({len(group_segments)} segments) · ⏱️ {group_timestamp}"
                else:
                    expander_title = (
                        f"🎤 {speaker_name} ({len(group_segments)} segments)"
                    )

                with st.expander(expander_title, expanded=True):
                    for segment in group_segments:
                        text = segment.get("text", "")
                        st.write(text)
                        if "sentiment" in segment:
                            sentiment = segment["sentiment"]
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.caption(
                                    f"Sentiment: {sentiment.get('compound', 0):.2f}"
                                )
                            with col2:
                                st.caption(f"Positive: {sentiment.get('pos', 0):.2f}")
                            with col3:
                                st.caption(f"Negative: {sentiment.get('neg', 0):.2f}")
                        if "emotion" in segment:
                            st.caption(f"Emotion: {segment['emotion']}")

        # Analysis modules: view dropdown + button grid (synced via session_state)
        st.session_state.setdefault("analysis_artifacts_version", 0)
        st.session_state.setdefault("analysis_run_in_progress", False)
        artifacts_version = st.session_state.get("analysis_artifacts_version", 0)
        modules = get_analysis_modules(selected)
        st.divider()
        st.subheader("📊 Analysis Modules")
        if not modules:
            st.info(
                "No analysis modules run yet. Use **Run analysis** below to generate results."
            )
        else:
            # Dropdown: key includes artifacts_version so list refreshes after run
            select_key = f"analysis_module_select_{selected}_{artifacts_version}"
            current_module = st.session_state.get("analysis_module")
            default_index = (
                modules.index(current_module)
                if current_module and current_module in modules
                else 0
            )
            chosen = st.selectbox(
                "View analysis module",
                options=modules,
                index=default_index,
                format_func=lambda m: build_module_label(m),
                key=select_key,
            )
            if chosen:
                st.session_state["analysis_module"] = chosen
                st.session_state["analysis_session"] = selected
            # Button grid: select which module to view (viewing is on Transcript via other pages)
            cols = st.columns(min(len(modules), 4))
            for idx, module in enumerate(modules):
                with cols[idx % 4]:
                    if st.button(module, key=f"module_{module}", width="stretch"):
                        st.session_state["analysis_module"] = module
                        st.session_state["analysis_session"] = selected
                        st.rerun()

        if not modules:
            st.info(
                "No analysis modules run yet. To run analysis, use the CLI: `transcriptx analyze`"
            )

        st.divider()
        with st.expander("✨ Highlights", expanded=False):
            _render_highlights_section(run_root)
        with st.expander("🧾 Executive Summary", expanded=False):
            _render_summary_section(run_root)

    except Exception as e:
        logger.error(f"Error loading transcript: {e}", exc_info=True)
        st.error(f"Error loading transcript: {e}")
        st.exception(e)


def render_speakers_list():
    """Speakers list page."""
    st.markdown('<div class="main-header">👥 Speakers</div>', unsafe_allow_html=True)

    try:
        speakers = get_all_speakers()

        if not speakers:
            st.info("No speakers found in database")
            return

        st.metric("Total Speakers", len(speakers))

        # Create speakers dataframe
        speakers_df = pd.DataFrame(
            [
                {
                    "ID": s.get("id"),
                    "Name": s.get("name", "Unknown"),
                    "Display Name": s.get("display_name", ""),
                    "Email": s.get("email", ""),
                    "Organization": s.get("organization", ""),
                    "Verified": "✓" if s.get("is_verified") else "✗",
                }
                for s in speakers
            ]
        )

        # Search
        search_term = st.text_input("🔍 Search speakers", key="speaker_search")
        if search_term:
            speakers_df = speakers_df[
                speakers_df["Name"].str.contains(search_term, case=False, na=False)
                | speakers_df["Display Name"].str.contains(
                    search_term, case=False, na=False
                )
            ]

        # Speaker detail selector - use actual speaker names from database alphabetically
        if speakers:
            # Sort speakers alphabetically by name
            sorted_speakers = sorted(speakers, key=lambda s: s.get("name", "").lower())
            speaker_options = {None: "Select..."}
            for speaker in sorted_speakers:
                speaker_id = speaker.get("id")
                speaker_name = speaker.get("name", "Unknown")
                display_name = speaker.get("display_name")
                if display_name and display_name != speaker_name:
                    label = f"{speaker_name} ({display_name})"
                else:
                    label = speaker_name
                speaker_options[speaker_id] = label

            # Get previous selection if any
            prev_speaker_id = st.session_state.get("speaker_detail_selector", None)

            selected_id = st.selectbox(
                "Select a speaker to view",
                options=list(speaker_options.keys()),
                format_func=lambda x: speaker_options.get(x, "Select..."),
                key="speaker_detail_selector",
            )

            # Check if a speaker was selected (not None) and it's different from previous
            if selected_id is not None and selected_id != prev_speaker_id:
                st.session_state["selected_speaker_id"] = selected_id
                st.session_state["page"] = "Speaker Detail"
                st.rerun()

            # Display table with selection capability
            table_key = "speakers_table"
            st.dataframe(
                speakers_df,
                width="stretch",
                hide_index=True,
                selection_mode="single-row",
                key=table_key,
            )

            # Handle row selection
            try:
                if table_key in st.session_state:
                    table_state = st.session_state[table_key]
                    # Handle different possible state structures
                    if isinstance(table_state, dict):
                        selection = table_state.get("selection", {})
                        if isinstance(selection, dict):
                            selected_indices = selection.get("rows", [])
                        elif isinstance(selection, list):
                            selected_indices = selection
                        else:
                            selected_indices = []
                    else:
                        selected_indices = []

                    if selected_indices:
                        selected_idx = selected_indices[0]
                        if isinstance(selected_idx, dict):
                            selected_idx = selected_idx.get(
                                "index", selected_idx.get("row", 0)
                            )
                        if selected_idx < len(sorted_speakers):
                            selected_speaker = sorted_speakers[selected_idx]
                            selected_id = selected_speaker.get("id")
                            if selected_id:
                                st.session_state["selected_speaker_id"] = selected_id
                                st.session_state["page"] = "Speaker Detail"
                                # Clear selection to prevent re-triggering
                                if table_key in st.session_state and isinstance(
                                    st.session_state[table_key], dict
                                ):
                                    st.session_state[table_key]["selection"] = {
                                        "rows": []
                                    }
                                st.rerun()
            except Exception as e:
                # If selection handling fails, just continue - dropdown still works
                logger.debug(f"Row selection handling failed: {e}")

    except Exception as e:
        logger.error(f"Error loading speakers: {e}", exc_info=True)
        st.error(f"Error loading speakers: {e}")
        st.exception(e)


def render_speaker_detail():
    """Speaker detail page."""
    st.markdown(
        '<div class="main-header">👤 Speaker Details</div>', unsafe_allow_html=True
    )

    try:
        speaker_id = st.session_state.get("selected_speaker_id")
        if not speaker_id:
            st.warning("No speaker selected")
            if st.button("← Back to Speakers"):
                st.session_state["page"] = "Speakers"
                st.rerun()
            return

        # Load speaker data
        speaker = get_speaker_by_id(speaker_id)
        if not speaker:
            st.error(f"Speaker {speaker_id} not found")
            return

        # Back button
        if st.button("← Back to Speakers"):
            st.session_state["page"] = "Speakers"
            st.rerun()

        # Display speaker info
        col1, col2 = st.columns([1, 3])

        with col1:
            st.subheader(speaker.get("name", "Unknown"))
            if speaker.get("display_name"):
                st.caption(speaker.get("display_name"))
            if speaker.get("email"):
                st.write(f"📧 {speaker.get('email')}")
            if speaker.get("organization"):
                st.write(f"🏢 {speaker.get('organization')}")
            if speaker.get("role"):
                st.write(f"💼 {speaker.get('role')}")
            if speaker.get("color"):
                st.write(f"🎨 Color: {speaker.get('color')}")

        with col2:
            # Statistics
            try:
                stats = get_speaker_statistics(speaker_id)
                if stats:
                    st.subheader("Statistics")
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric(
                            "Total Words", f"{stats.get('total_word_count', 0):,}"
                        )
                    with col2:
                        st.metric("Segments", stats.get("total_segment_count", 0))
                    with col3:
                        st.metric(
                            "Speaking Time",
                            f"{stats.get('total_speaking_time', 0) / 60:.1f} min",
                        )
                    with col4:
                        st.metric(
                            "Avg Rate",
                            f"{stats.get('average_speaking_rate', 0):.1f} wpm",
                        )

                    # Additional stats
                    if stats.get("average_sentiment_score") is not None:
                        st.metric(
                            "Avg Sentiment",
                            f"{stats.get('average_sentiment_score', 0):.2f}",
                        )
                    if stats.get("dominant_emotion"):
                        st.metric("Dominant Emotion", stats.get("dominant_emotion"))
            except Exception as e:
                logger.warning(f"Could not load statistics: {e}")
                st.warning(f"Could not load statistics: {e}")

        # Profiles
        try:
            profiles = get_speaker_profiles(speaker_id)
            if profiles:
                st.subheader("📊 Analysis Profiles")
                formatted_profiles = format_speaker_profile_data(profiles)

                for profile_type, profile_data in formatted_profiles.items():
                    with st.expander(f"{profile_type.replace('_', ' ').title()}"):
                        st.json(profile_data)
        except Exception as e:
            logger.debug(f"Could not load profiles: {e}")

        # Exemplars
        try:
            render_speaker_exemplars(speaker_id)
        except Exception as e:
            logger.warning(f"Could not load speaker exemplars: {e}")

        # Conversations
        try:
            conversations = get_speaker_conversations(speaker_id)
            if conversations:
                st.subheader("💬 Conversations")
                for conv in conversations:
                    with st.expander(f"Session: {conv.get('session_name', 'Unknown')}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Words:** {conv.get('word_count', 0):,}")
                        with col2:
                            st.write(
                                f"**Duration:** {conv.get('speaking_time', 0) / 60:.1f} min"
                            )
        except Exception as e:
            logger.warning(f"Could not load conversations: {e}")

    except Exception as e:
        logger.error(f"Error loading speaker details: {e}", exc_info=True)
        st.error(f"Error loading speaker details: {e}")
        st.exception(e)


# Main app
def main():
    """Main application entry point."""

    # Initialize session state
    if "page" not in st.session_state:
        st.session_state["page"] = "Overview"
    st.session_state.setdefault("analysis_artifacts_version", 0)
    st.session_state.setdefault("analysis_run_in_progress", False)

    load_error = None
    try:
        session_map, sessions_list = _get_cached_session_data()
    except Exception as e:
        logger.warning(f"Failed to load session list: {e}", exc_info=True)
        load_error = str(e)
        session_map = {}
        sessions_list = []

    # Always render sidebar first so the menu is visible even with no sessions or on error
    current_page = st.session_state.get("page", "Home")

    def _nav_button(page_key: str, label: str) -> None:
        """Render a single nav button; bold + highlighted when active."""
        is_active = current_page == page_key
        text = f"**{label}**" if is_active else label
        if is_active:
            st.markdown('<div class="nav-active-item">', unsafe_allow_html=True)
        if st.button(text, key=f"nav_{page_key}", width="stretch", type="secondary"):
            st.session_state["page"] = page_key
            st.rerun()
        if is_active:
            st.markdown("</div>", unsafe_allow_html=True)

    def _section(label: str) -> None:
        st.markdown(
            f'<p class="nav-section-header">{label}</p>', unsafe_allow_html=True
        )

    def _subject_section(label: str) -> None:
        st.markdown(
            f'<p class="subject-section-header">{label}</p>', unsafe_allow_html=True
        )

    with st.sidebar:
        st.title("TranscriptX")
        st.divider()

        # ── WORKSPACE ────────────────────────────────────────────────────────
        _section("Workspace")
        _nav_button("Home", "Home")
        _nav_button("Library", "Library")
        _nav_button("Search", "Search")

        # ── PIPELINE ─────────────────────────────────────────────────────────
        _section("Pipeline")
        _nav_button("Audio Prep", "Audio Prep")
        _nav_button("Audio Merge", "Audio Merge")
        _nav_button("Speaker ID", "Speaker ID")
        _nav_button("Run Analysis", "Run Analysis")
        _nav_button("Batch Ops", "Batch Ops")

        # ── EXPLORE ──────────────────────────────────────────────────────────
        _section("Explore")
        _nav_button("Statistics", "Statistics")
        _nav_button("Speakers", "Speakers")
        _nav_button("Groups", "Groups")

        # ── TOOLS ────────────────────────────────────────────────────────────
        tools_items = []
        if _speaker_studio_available:
            tools_items.append(("Speaker Studio", "Speaker Studio"))
        if _corrections_studio_available:
            tools_items.append(("Corrections Studio", "Corrections Studio"))
        if tools_items:
            _section("Tools")
            for page_key, label in tools_items:
                _nav_button(page_key, label)

        # ── SYSTEM ───────────────────────────────────────────────────────────
        _section("System")
        _nav_button("Profiles", "Profiles")
        _nav_button("Settings", "Settings")
        _nav_button("Diagnostics", "Diagnostics")

        st.divider()

        # ── SUBJECT PANEL ────────────────────────────────────────────────────
        st.markdown("**Subject**")

        _subject_section("Context")
        subject_type_label = st.radio(
            "Type",
            ["Transcript", "Group"],
            index=0,
            horizontal=True,
            key="subject_type_selector",
            label_visibility="collapsed",
        )
        subject_type = "transcript" if subject_type_label == "Transcript" else "group"
        st.session_state["subject_type"] = subject_type

        if subject_type == "transcript":
            if not sessions_list:
                st.caption("No transcripts yet")
                st.session_state["subject_id"] = None
            else:
                session_options = sorted(session_map.keys())
                selected_session = st.selectbox(
                    "Transcript", session_options, key="subject_id_selector"
                )
                st.session_state["subject_id"] = selected_session
        else:
            try:
                from transcriptx.web.services.group_service import GroupService

                groups = GroupService.list_groups()
            except Exception:
                groups = []
            if not groups:
                st.caption("No groups yet")
                st.session_state["subject_id"] = None
            else:
                group_options = {g.uuid: g for g in groups}
                group_labels = {
                    g.uuid: f"{g.name or 'Unnamed'} • {len(g.transcript_file_uuids or [])} transcripts"
                    for g in groups
                }
                selected_group = st.selectbox(
                    "Group",
                    list(group_options.keys()),
                    format_func=lambda key: group_labels.get(key, key),
                    key="subject_id_selector",
                )
                st.session_state["subject_id"] = selected_group

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
                st.session_state["run_id"] = selected_run_id
            else:
                st.caption("No runs yet")
                st.session_state["run_id"] = None
        else:
            st.session_state["run_id"] = None

        # ── VIEWS ────────────────────────────────────────────────────────────
        _subject_section("Views")
        _nav_button("Overview", "Overview")
        _nav_button("Transcript", "Transcript")
        _nav_button("Charts", "Charts")
        _nav_button("Insights", "Insights")
        _nav_button("Data", "Data")

        # ── FILES ────────────────────────────────────────────────────────────
        _subject_section("Files")
        _nav_button("Explorer", "File List")

        # ── ADVANCED ─────────────────────────────────────────────────────────
        _subject_section("Advanced")
        _nav_button("Configuration", "Configuration")

        st.divider()
        st.caption("TranscriptX")

    # Main content: show load error if present, then route to page
    if load_error:
        st.error(f"Could not load session list: {load_error}")

    current_page = st.session_state.get("page", "Home")

    # Route to appropriate page
    try:
        viewer_pages = {
            "Overview",
            "Transcript",
            "Charts",
            "Insights",
            "Data",
            "Explorer",
            "Configuration",
        }
        if current_page in viewer_pages:
            subject = SubjectService.resolve_current_subject(st.session_state)
            if subject:
                render_subject_header(subject)
        if current_page == "Home":
            render_home()
        elif current_page == "Library":
            render_library()
        elif current_page == "Overview":
            render_overview()
        elif current_page == "Transcript":
            render_transcript_viewer()
        elif current_page == "Search":
            render_search()
        elif current_page == "Insights":
            render_insights()
        elif current_page == "Charts":
            render_charts()
        elif current_page == "Data":
            render_data()
        elif current_page == "Explorer":
            render_explorer()
        elif current_page == "Run Analysis":
            render_run_analysis_page()
        elif current_page == "Settings":
            render_settings_page()
        elif current_page == "Profiles":
            render_profiles_page()
        elif current_page == "Speaker ID":
            render_speaker_id_page()
        elif current_page == "Audio Prep":
            render_audio_prep_page()
        elif current_page == "Audio Merge":
            render_audio_merge_page()
        elif current_page == "Batch Ops":
            render_batch_ops_page()
        elif current_page == "Diagnostics":
            render_diagnostics_page()
        elif current_page == "Speakers":
            render_speakers_list()
        elif current_page == "Configuration":
            render_configuration_page()
        elif current_page == "Groups":
            render_groups()
        elif current_page == "Statistics":
            render_statistics()
        elif (
            current_page == "Speaker Studio"
            and _speaker_studio_available
            and render_speaker_studio
        ):
            render_speaker_studio()
        elif (
            current_page == "Corrections Studio"
            and _corrections_studio_available
            and render_corrections_studio
        ):
            render_corrections_studio()
        elif current_page == "Speaker Detail":
            render_speaker_detail()
    except Exception as e:
        logger.error(f"Error in main app: {e}", exc_info=True)
        st.error(f"An unexpected error occurred: {e}")
        st.exception(e)


if __name__ == "__main__":
    main()
