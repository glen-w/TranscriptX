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
        load_transcript_data,
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
    from transcriptx.web.services import FileService, ArtifactService
    from transcriptx.web.page_modules.overview import render_overview
    from transcriptx.web.page_modules.charts import render_charts
    from transcriptx.web.page_modules.data import render_data
    from transcriptx.web.page_modules.explorer import render_explorer
    from transcriptx.web.page_modules.groups import render_groups
    from transcriptx.web.page_modules.statistics import render_statistics
    from transcriptx.web.page_modules.search import render_search
    from transcriptx.web.page_modules.insights import (
        render_insights,
        _render_highlights_section,
        _render_summary_section,
    )
    from transcriptx.web.models.search import NavRequest, SegmentRef
    from transcriptx.web.pages.configuration import render_configuration_page
    from transcriptx.web.components.exemplars import render_speaker_exemplars
    from transcriptx.core.utils.paths import OUTPUTS_DIR, DIARISED_TRANSCRIPTS_DIR
    from transcriptx.core.utils.logger import get_logger
    from transcriptx.utils.text_utils import format_time_detailed
    from transcriptx.web.module_registry import (
        get_all_available_modules,
        build_module_label,
    )
    from transcriptx.core.analysis.selection import (
        apply_analysis_mode_settings,
        filter_modules_by_mode,
        get_recommended_modules,
        VALID_MODES,
        VALID_PROFILES,
    )
    from transcriptx.core.pipeline.module_registry import get_module_info
    from transcriptx.core import run_analysis_pipeline
    from transcriptx.core.pipeline.target_resolver import TranscriptRef
    from transcriptx.core.utils.audio_availability import has_resolvable_audio
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
    /* Style navigation buttons to look like text links */
    div[data-testid="stButton"] > button[kind="secondary"] {
        background: transparent;
        border: none;
        color: #1f77b4;
        text-align: left;
        padding: 0.5rem 0;
        font-weight: normal;
        box-shadow: none;
        width: 100%;
    }
    div[data-testid="stButton"] > button[kind="secondary"]:hover {
        color: #0d5a8a;
        text-decoration: underline;
        background: transparent;
    }
    div[data-testid="stButton"] > button[kind="secondary"]:focus {
        box-shadow: none;
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
    st.session_state["selected_session"] = segment_ref.transcript_ref.session_slug
    st.session_state["selected_run_id"] = segment_ref.transcript_ref.run_id
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
        sessions = list_available_sessions()
        if not sessions:
            st.warning("No sessions available")
            return

        # Session selector - prefer global state if set
        selected_session = st.session_state.get("selected_session")
        selected_run_id = st.session_state.get("selected_run_id")
        if selected_session and selected_run_id:
            selected = f"{selected_session}/{selected_run_id}"
        else:
            session_names = [s["name"] for s in sessions]
            selected = st.selectbox(
                "Select Session", session_names, key="transcript_session_selector"
            )

        if not selected:
            return

        # Clear state after using it
        if "selected_session" in st.session_state and "selected_run_id" in st.session_state:
            del st.session_state["selected_session"]
            del st.session_state["selected_run_id"]

        # Load transcript
        with st.spinner(f"Loading transcript for {selected}..."):
            transcript_data = load_transcript_data(selected)

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
        session_output_dir = Path(OUTPUTS_DIR) / selected
        transcripts_dir = session_output_dir / "transcripts"
        manifest_path = session_output_dir / ".transcriptx" / "manifest.json"
        manifest_transcript_path = None
        base_name = None
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as handle:
                    manifest = json.load(handle)
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
                value=st.session_state["show_timestamps"],
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
                speaker = segment.get("speaker_display") or segment.get("speaker", "Unknown")
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
                    expander_title = f"🎤 {speaker_name} ({len(group_segments)} segments)"
                
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
                                st.caption(
                                    f"Negative: {sentiment.get('neg', 0):.2f}"
                                )
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
                    if st.button(
                        module, key=f"module_{module}", width='stretch'
                    ):
                        st.session_state["analysis_module"] = module
                        st.session_state["analysis_session"] = selected
                        st.rerun()

        # View-only: run analysis lives on the dedicated "Run Analysis" page (sidebar).
        if not modules:
            st.info(
                "No analysis modules run yet. Go to **Run Analysis** in the sidebar to generate results."
            )

        st.divider()
        with st.expander("✨ Highlights", expanded=False):
            _render_highlights_section(selected_session, selected_run_id)
        with st.expander("🧾 Executive Summary", expanded=False):
            _render_summary_section(selected_session, selected_run_id)

    except Exception as e:
        logger.error(f"Error loading transcript: {e}", exc_info=True)
        st.error(f"Error loading transcript: {e}")
        st.exception(e)


def render_run_analysis_page():
    """
    Dedicated page to run analysis on the session selected in the sidebar.

    Non-goal: This run flow is synchronous and in-process; long-running jobs
    are not yet queued or resumable.
    """
    st.markdown(
        '<div class="main-header">▶ Run Analysis</div>', unsafe_allow_html=True
    )
    st.caption(
        "Run the analysis pipeline on the session selected in the sidebar. "
        "Results will be available in the Transcript view after completion."
    )

    selected_session = st.session_state.get("selected_session")
    selected_run_id = st.session_state.get("selected_run_id")
    if not selected_session or not selected_run_id:
        st.warning(
            "Select a **Session** and **Run** in the sidebar first, then run analysis here."
        )
        return

    selected = f"{selected_session}/{selected_run_id}"
    transcript_path = FileService.resolve_transcript_path(selected)
    if transcript_path is None:
        st.warning(
            "Could not resolve transcript path for this session. Run analysis is unavailable."
        )
        return

    # Build context for module labels (audio + voice deps)
    try:
        from transcriptx.core.utils.config import get_config
        from transcriptx.core.analysis.voice.deps import check_voice_optional_deps
        _cfg = get_config()
        _voice_cfg = getattr(getattr(_cfg, "analysis", None), "voice", None)
        _egemaps = bool(getattr(_voice_cfg, "egemaps_enabled", True))
        _deps = check_voice_optional_deps(egemaps_enabled=_egemaps)
        _audio_available = has_resolvable_audio([str(transcript_path)])
        _missing_deps = (
            _deps.get("missing_optional_deps", [])
            if not _deps.get("ok")
            else []
        )
        _context = {
            "audio_available": _audio_available,
            "missing_deps": _missing_deps,
        }
    except Exception:
        _context = {}

    run_mode = st.radio(
        "Mode",
        options=list(VALID_MODES),
        format_func=lambda x: "Quick (faster)" if x == "quick" else "Full (comprehensive)",
        key="run_analysis_mode",
        horizontal=True,
    )
    run_profile = None
    if run_mode == "full":
        run_profile = st.selectbox(
            "Profile",
            options=list(VALID_PROFILES),
            format_func=lambda x: x.capitalize(),
            key="run_analysis_profile",
        )
    preset = st.radio(
        "Preset",
        options=["recommended", "all", "light_only", "custom"],
        format_func=lambda x: {
            "recommended": "Recommended",
            "all": "All modules",
            "light_only": "Light modules only",
            "custom": "Custom",
        }.get(x, x),
        key="run_analysis_preset",
        horizontal=True,
    )
    all_available = get_all_available_modules()
    if preset == "custom":
        try:
            _missing = _context.get("missing_deps") or []

            def _dep_resolver(info):
                if not getattr(info, "requires_audio", False):
                    return True
                return not _missing

            _runnable = get_recommended_modules(
                [str(transcript_path)],
                audio_resolver=has_resolvable_audio,
                dep_resolver=_dep_resolver,
                include_heavy=True,
                include_excluded_from_default=True,
            )
        except Exception:
            _runnable = get_recommended_modules(
                [str(transcript_path)],
                audio_resolver=has_resolvable_audio,
                include_heavy=True,
                include_excluded_from_default=True,
            )
        _runnable_set = set(_runnable)
        _unavailable = sorted(m for m in all_available if m not in _runnable_set)
        _default_custom = [
            m
            for m in get_recommended_modules(
                [str(transcript_path)],
                audio_resolver=has_resolvable_audio,
                include_excluded_from_default=True,
            )[:5]
            if m in _runnable_set
        ]
        custom_options = st.multiselect(
            "Modules",
            options=sorted(_runnable_set),
            default=_default_custom,
            format_func=lambda m: build_module_label(m, context=_context),
            key="run_analysis_custom_modules",
        )
        if _unavailable:
            _audio_ok = _context.get("audio_available", None)
            _deps_ok = not (_context.get("missing_deps") or [])
            if _audio_ok is False and not _deps_ok:
                _reason = "audio missing and voice deps missing"
            elif _audio_ok is False:
                _reason = "audio missing for this session"
            elif not _deps_ok:
                _reason = "voice deps missing"
            else:
                _reason = "unavailable for this session"
            st.caption(
                f"Unavailable ({_reason}): " + ", ".join(_unavailable)
            )
        run_modules = custom_options
    elif preset == "all":
        run_modules = all_available
    elif preset == "light_only":
        run_modules = [
            m
            for m in all_available
            if get_module_info(m) and get_module_info(m).category == "light"
        ]
    else:
        run_modules = get_recommended_modules(
            [str(transcript_path)],
            audio_resolver=has_resolvable_audio,
        )
    filtered_modules = filter_modules_by_mode(run_modules, run_mode)
    open_after = st.checkbox(
        "Open results after run",
        value=True,
        key="run_analysis_open_after",
    )
    run_disabled = (
        st.session_state.get("analysis_run_in_progress", False)
        or not filtered_modules
    )
    run_clicked = st.button(
        "Run analysis",
        key="run_analysis_btn",
        disabled=run_disabled,
    )
    if not filtered_modules and preset == "custom":
        st.caption("Select at least one module to run.")
    if not filtered_modules and preset == "light_only":
        st.caption("No light-category modules available for this run.")
    if run_clicked and filtered_modules:
        st.session_state["analysis_run_in_progress"] = True
        apply_analysis_mode_settings(run_mode, profile=run_profile)
        logger.info(
            "Run analysis: transcript_path=%s mode=%s profile=%s modules=%s",
            str(transcript_path),
            run_mode,
            run_profile or "",
            filtered_modules,
        )
        try:
            with st.spinner("Running analysis pipeline…"):
                run_analysis_pipeline(
                    target=TranscriptRef(path=str(transcript_path)),
                    selected_modules=filtered_modules,
                    skip_speaker_mapping=True,
                    persist=False,
                )
            st.session_state["analysis_artifacts_version"] = (
                st.session_state.get("analysis_artifacts_version", 0) + 1
            )
            if open_after and filtered_modules:
                st.session_state["analysis_module"] = filtered_modules[0]
                st.session_state["analysis_session"] = selected
            st.success("Analysis completed.")
        except Exception as e:
            logger.error(f"Run analysis failed: {e}", exc_info=True)
            st.error(f"Analysis failed: {e}")
        finally:
            st.session_state["analysis_run_in_progress"] = False
        st.rerun()


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
            selected_rows = st.dataframe(
                speakers_df,
                width='stretch',
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
    has_sessions = bool(sessions_list)

    # Always render sidebar first so the menu is visible even with no sessions or on error
    current_page = st.session_state.get("page", "Overview")
    with st.sidebar:
        st.title("TranscriptX")
        st.divider()

        # Global navigation (no subheader)
        global_pages = [
            ("Search", "Search"),
            ("Speakers", "Speakers"),
            ("Groups", "Groups"),
            ("Statistics", "Statistics"),
        ]
        for page_key, label in global_pages:
            text = f"**{label}**" if current_page == page_key else label
            if st.button(
                text,
                key=f"nav_{page_key}",
                width='stretch',
                type="secondary",
            ):
                st.session_state["page"] = page_key
                st.rerun()

        st.divider()

        # Transcript section (session/run selectors only when we have sessions)
        st.markdown("**Transcript**")
        if has_sessions:
            session_options = sorted(session_map.keys())
            selected_session = st.selectbox(
                "Session", session_options, key="session_selector"
            )
            run_options = [s["run_id"] for s in session_map.get(selected_session, [])]
            selected_run_id = st.selectbox("Run", run_options, key="run_selector")
            st.session_state["selected_session"] = selected_session
            st.session_state["selected_run_id"] = selected_run_id
        else:
            st.caption("No sessions yet")
            st.session_state["selected_session"] = None
            st.session_state["selected_run_id"] = None

        # Transcript-specific navigation
        transcript_pages = [
            ("Overview", "Overview"),
            ("Transcript", "Transcript"),
            ("Run Analysis", "Run Analysis"),
            ("Charts", "Charts"),
            ("Insights", "Insights"),
            ("Data", "Data"),
            ("Explorer", "File List"),
            ("Configuration", "Configuration"),
        ]
        for page_key, label in transcript_pages:
            text = f"**{label}**" if current_page == page_key else label
            if st.button(
                text,
                key=f"nav_{page_key}",
                width='stretch',
                type="secondary",
            ):
                st.session_state["page"] = page_key
                st.rerun()

        st.divider()
        st.caption("Streamlit Studio Interface")

    # Main content: show message if no sessions or load error, otherwise route to page
    if not has_sessions:
        if load_error:
            st.error(f"Could not load session list: {load_error}")
        else:
            st.info("No transcript sessions found. Process transcripts to see them here.")
        return

    current_page = st.session_state.get("page", "Overview")

    # Route to appropriate page
    try:
        if current_page == "Overview":
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
        elif current_page == "Speakers":
            render_speakers_list()
        elif current_page == "Configuration":
            render_configuration_page()
        elif current_page == "Groups":
            render_groups()
        elif current_page == "Statistics":
            render_statistics()
        elif current_page == "Speaker Detail":
            render_speaker_detail()
    except Exception as e:
        logger.error(f"Error in main app: {e}", exc_info=True)
        st.error(f"An unexpected error occurred: {e}")
        st.exception(e)


if __name__ == "__main__":
    main()
