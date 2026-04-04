"""
Streamlit-based web interface for TranscriptX.

This replaces the Flask/Jinja2 web interface with a simpler, more maintainable
Streamlit implementation.

To run:
    streamlit run src/transcriptx/web/app.py
"""

# Load .env before any transcriptx imports so TRANSCRIPTX_* paths are correct
from transcriptx._bootstrap import bootstrap

bootstrap()

import html
import json
import os
import streamlit as st
from pathlib import Path
from typing import List, Optional

# Import existing utilities
try:
    from transcriptx.web.utils import (
        list_available_sessions,
        load_transcript_by_session,
        get_analysis_modules,
    )
    from transcriptx.web.services import (
        FileService,
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
    from transcriptx.web.page_modules.upload_transcript import (
        render_upload_transcript_page,
    )
    from transcriptx.web.page_modules.transcribe_audio import (
        render_transcribe_audio_page,
    )
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
    from transcriptx.web.components.context_bar import render_context_bar
    from transcriptx.web.shell import configure_streamlit_page, inject_global_styles
    from transcriptx.core.utils.paths import DIARISED_TRANSCRIPTS_DIR
    from transcriptx.core.utils.logger import get_logger
    from transcriptx.utils.text_utils import format_time_detailed
    from transcriptx.web.module_registry import build_module_label
except ImportError as e:
    st.error(f"Import error: {e}")
    st.stop()

from transcriptx.web.state import (
    PAGE_FLASH_KIND,
    PAGE_FLASH_MESSAGE,
    SELECTBOX_PLACEHOLDER_GROUP,
    SELECTBOX_PLACEHOLDER_TRANSCRIPT,
    try_page_toast,
)

logger = get_logger()

configure_streamlit_page()
inject_global_styles()


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


def _session_list_covers_transcript_path(
    sessions_list: list, transcript_path: Path
) -> bool:
    """True if some session resolves to the same file on disk (including samefile)."""
    try:
        target = transcript_path.expanduser().resolve()
    except (OSError, RuntimeError):
        return False
    for s in sessions_list:
        name = s.get("name", "")
        if "/" not in name:
            continue
        resolved = FileService.resolve_transcript_path(name)
        if resolved is None:
            continue
        try:
            rp = resolved.resolve()
        except (OSError, RuntimeError):
            continue
        if rp == target:
            return True
        try:
            if os.path.samefile(rp, target):
                return True
        except (OSError, ValueError):
            continue
    return False


def _slug_display_labels_from_index() -> dict[str, str]:
    """Map output folder slug -> friendly basename (matches library / Run Analysis naming)."""
    from transcriptx.core.utils.slug_manager import load_index

    labels: dict[str, str] = {}
    for _tk, entry in load_index().get("transcripts", {}).items():
        slug = entry.get("slug")
        basename = entry.get("source_basename")
        if slug and basename:
            labels[slug] = basename
    return labels


def _get_transcript_dropdown_options():
    """
    Merge sessions (from outputs) and raw transcripts (from configured folder).
    Returns (options_list, format_func) for st.selectbox.
    Raw transcripts from the configured folder appear so users can select
    transcripts that have not been run through the pipeline yet.
    """
    session_map, sessions_list = _get_cached_session_data()
    session_slugs = set(session_map.keys())
    slug_labels = _slug_display_labels_from_index()

    # Managed transcripts from configured folder (LibraryController uses discover_managed_transcript_paths)
    try:
        from transcriptx.web.cache_helpers import get_cached_list_transcripts

        raw = get_cached_list_transcripts()
    except Exception:
        raw = []

    options: list[str] = []
    options.extend(session_slugs)
    # Raw transcripts not already represented by a session (same file on disk)
    for t in raw:
        try:
            tp = Path(t.path).expanduser().resolve()
        except (OSError, RuntimeError):
            continue
        if not _session_list_covers_transcript_path(sessions_list, tp):
            options.append(str(tp))

    def _format(opt: str) -> str:
        p = Path(opt)
        if p.is_absolute() and p.suffix.lower() == ".json":
            return p.stem  # Raw transcript path: show base name
        # Folder slug may be disambiguated (__2); show index basename like Run Analysis
        return slug_labels.get(opt, opt)

    options.sort(key=lambda o: (_format(o).lower(), str(o)))
    return options, _format


def _format_timestamp_range(start: float, end: float, format_key: str) -> str:
    if format_key == "seconds":
        return f"{start:.1f}s - {end:.1f}s"
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
    from transcriptx.web.components.empty_state import render_empty_state
    from transcriptx.web.components.page_shell import (
        render_page_help,
        render_page_shell,
    )

    _transcript_help = (
        "**What this shows:** Segments for the selected transcript run.\n\n"
        "**Search** filters the list. Use **Plain** for line-by-line reading or "
        "**Segmented** for speaker blocks."
    )

    def _transcript_page_help() -> None:
        render_page_help(_transcript_help)

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
        subject = SubjectService.resolve_current_subject(st.session_state)
        run_id = st.session_state.get("run_id")
        if not subject:
            render_empty_state(
                "missing_prerequisite",
                "No subject selected",
                "Choose a transcript or group in the sidebar, then pick a run.",
                primary_action=("Open Library", "Library"),
                secondary_action=("Run Analysis", "Run Analysis"),
            )
            _transcript_page_help()
            return
        if subject.subject_type == "group":
            st.subheader("Group transcripts")
            if not subject.members:
                st.info("This group has no transcripts.")
                _transcript_page_help()
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
            _transcript_page_help()
            return
        if subject.subject_type != "transcript":
            render_empty_state(
                "missing_prerequisite",
                "Transcript view needs a transcript subject",
                "Switch the sidebar context to **Transcript** or open a member from **Groups**.",
                primary_action=("Groups", "Groups"),
                secondary_action=("Overview", "Overview"),
            )
            _transcript_page_help()
            return
        if not run_id:
            render_empty_state(
                "missing_prerequisite",
                "No run selected",
                "Select a run for this transcript in the sidebar.",
                primary_action=("Run Analysis", "Run Analysis"),
                secondary_action=("Overview", "Overview"),
            )
            _transcript_page_help()
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
            _transcript_page_help()
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
                # Tooltip: show resolved speaker names when hovering the speaker count.
                segments_for_names = transcript_data.get("segments", []) or []
                speaker_names = []
                try:
                    for seg in segments_for_names:
                        if not isinstance(seg, dict):
                            continue
                        name = seg.get("speaker_display") or seg.get("speaker")
                        if not name:
                            continue
                        speaker_names.append(str(name).strip())
                except Exception:
                    speaker_names = []
                speaker_names = sorted({n for n in speaker_names if n})
                speaker_help = None
                if speaker_names:
                    speaker_help = "Speakers:\n" + "\n".join(
                        f"- {n}" for n in speaker_names
                    )
                st.metric(
                    "Speakers",
                    metadata.get("speaker_count", 0),
                    help=speaker_help,
                )
            with col3:
                segments_for_words = transcript_data.get("segments", []) or []
                seg_count = len(segments_for_words)
                total_words = 0
                try:
                    for seg in segments_for_words:
                        if not isinstance(seg, dict):
                            continue
                        text = seg.get("text") or ""
                        total_words += len(str(text).split())
                except Exception:
                    total_words = 0
                avg_words = (total_words / seg_count) if seg_count else 0.0
                segments_help = f"Total words: {total_words:,}\nAverage words/segment: {avg_words:.1f}"
                st.metric("Segments", seg_count, help=segments_help)
            with col4:
                st.metric("Language", metadata.get("language", "Unknown"))

        # Download actions
        download_label_col, txt_col, csv_col, json_col = st.columns([2, 1, 1, 1])

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

        with download_label_col:
            st.markdown("📥 Download:")

        with txt_col:
            if txt_file and txt_file.exists():
                with open(txt_file, "rb") as f:
                    st.download_button(
                        label="TXT",
                        data=f.read(),
                        file_name=txt_file.name,
                        mime="text/plain",
                        key="download_txt",
                        type="tertiary",
                    )
            else:
                st.caption("TXT")

        with csv_col:
            if csv_file and csv_file.exists():
                with open(csv_file, "rb") as f:
                    st.download_button(
                        label="CSV",
                        data=f.read(),
                        file_name=csv_file.name,
                        mime="text/csv",
                        key="download_csv",
                        type="tertiary",
                    )
            else:
                st.caption("CSV")

        with json_col:
            if json_file and json_file.exists():
                with open(json_file, "rb") as f:
                    st.download_button(
                        label="JSON",
                        data=f.read(),
                        file_name=json_file.name,
                        mime="application/json",
                        key="download_json",
                        type="tertiary",
                    )
            else:
                # Fallback: generate JSON from current data
                transcript_json = json.dumps(transcript_data, indent=2, default=str)
                st.download_button(
                    label="JSON",
                    data=transcript_json,
                    file_name=f"{selected}_transcript.json",
                    mime="application/json",
                    key="download_json",
                    type="tertiary",
                )

        st.divider()

        # Resolve speaker names from sidecar maps and segment fields
        from transcriptx.web.utils import resolve_speaker_names_from_db

        segments = transcript_data.get("segments", [])
        if segments:
            segments = resolve_speaker_names_from_db(segments, selected)

        nav_request = st.session_state.get("nav_request")
        highlight_query = None
        jump_index = None
        if nav_request:
            highlight_query = nav_request.highlight_query
            segment_ref = nav_request.segment_ref
            if segment_ref.segment_index is not None:
                jump_index = segment_ref.segment_index
            st.session_state["nav_request"] = None

        if not segments:
            render_empty_state(
                "no_results_yet",
                "No segments in this transcript",
                "The transcript file may be empty or in an unexpected format.",
                primary_action=("Open Library", "Library"),
                secondary_action=None,
            )
            _transcript_page_help()
            return

        st.markdown('<div class="tx-transcript-controls">', unsafe_allow_html=True)
        search_text = st.text_input("🔍 Search in transcript", key="transcript_search")

        show_timestamps = st.checkbox(
            "Show timestamps",
            key="show_timestamps",
        )
        format_key = st.session_state.get("timestamp_format", "seconds")
        st.markdown("</div>", unsafe_allow_html=True)

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
            copy_chunks: list[str] = []
            for segment_index, segment in display_segments:
                speaker = segment.get("speaker_display") or segment.get(
                    "speaker", "Unknown"
                )
                text = segment.get("text", "")
                copy_chunks.append(text)
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
                chip = f'<span class="tx-speaker-chip">{html.escape(speaker)}</span>'
                if show_timestamps:
                    timestamp = _format_timestamp_range(start, end, format_key)
                    st.markdown(
                        f"{chip} · ⏱️ {html.escape(timestamp)}",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(chip, unsafe_allow_html=True)
                st.markdown(
                    '<div class="tx-segment-block">',
                    unsafe_allow_html=True,
                )
                if rendered_text != text:
                    st.markdown(rendered_text, unsafe_allow_html=True)
                else:
                    st.write(text)
                st.markdown("</div>", unsafe_allow_html=True)
                st.divider()
            if copy_chunks:
                joined = "\n\n".join(copy_chunks)
                st.download_button(
                    "Download visible segments as .txt",
                    data=joined,
                    file_name="transcript_snippet.txt",
                    mime="text/plain",
                    key="transcript_copy_visible_txt",
                )

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
                        group_start, group_end, format_key
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
                "No analysis modules run yet. Use the Run Analysis page to analyze this transcript."
            )

        st.divider()
        with st.expander("✨ Highlights", expanded=False):
            _render_highlights_section(run_root)
        with st.expander("🧾 Executive Summary", expanded=False):
            _render_summary_section(run_root)

        _transcript_page_help()

    except Exception as e:
        logger.error(f"Error loading transcript: {e}", exc_info=True)
        st.error(f"Error loading transcript: {e}")
        st.exception(e)
        _transcript_page_help()


def render_speakers_list():
    """Speakers list page removed in file-native mode."""
    st.info("Speaker pages were removed. Use transcript and group views instead.")


def render_speaker_detail():
    """Speaker detail page removed in file-native mode."""
    st.info("Speaker pages were removed. Use transcript and group views instead.")


def _consume_page_flash() -> None:
    """Show one-shot flash banner and optional toast; clear keys."""
    if PAGE_FLASH_MESSAGE not in st.session_state:
        return
    msg = st.session_state.pop(PAGE_FLASH_MESSAGE, "")
    kind = st.session_state.pop(PAGE_FLASH_KIND, "info")
    if not msg:
        return
    if kind == "success":
        st.success(msg)
    elif kind == "warning":
        st.warning(msg)
    elif kind == "error":
        st.error(msg)
    else:
        st.info(msg)
    try_page_toast(msg)


# Main app
def main():
    """Main application entry point."""

    # Initialize session state
    if "page" not in st.session_state:
        st.session_state["page"] = "Overview"
    if st.session_state.get("page") == "Configuration":
        st.session_state["page"] = "Settings"
        st.rerun()
    st.session_state.setdefault("analysis_artifacts_version", 0)
    st.session_state.setdefault("analysis_run_in_progress", False)

    load_error = None
    try:
        session_map, sessions_list = _get_cached_session_data()
    except Exception as e:
        logger.warning(f"Failed to load session list: {e}", exc_info=True)
        load_error = str(e)
        session_map = {}  # noqa: F841
        sessions_list = []  # noqa: F841

    # Always render sidebar first so the menu is visible even with no sessions or on error
    current_page = st.session_state.get("page", "Home")

    def _nav_button(page_key: str, label: str, *, key_suffix: str = "") -> None:
        """Render a single nav button; bold + highlighted when active.

        ``key_suffix`` disambiguates duplicate shortcuts (e.g. Browse vs subject Views)
        so Streamlit widget keys stay unique.
        """
        is_active = current_page == page_key
        text = f"**{label}**" if is_active else label
        if is_active:
            st.markdown('<div class="nav-active-item">', unsafe_allow_html=True)
        btn_key = f"nav_{page_key}{key_suffix}"
        if st.button(text, key=btn_key, width="stretch", type="secondary"):
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
        st.markdown("### 🎙️ TranscriptX")
        _nav_button("Home", "Home")
        _nav_button("Library", "Library")
        _nav_button("Search", "Search")

        _section("Workflow")
        _nav_button("Transcribe Audio", "Transcribe Audio")
        _nav_button("Import Transcript", "Import Transcript")
        _nav_button("Speaker ID", "Speaker Identification")
        _nav_button("Run Analysis", "Run Analysis")
        _nav_button("Batch Ops", "Batch Analysis")
        _nav_button("Groups", "Groups")

        _section("Tools")
        if _corrections_studio_available:
            _nav_button("Corrections Studio", "Corrections Studio")
        _nav_button("Audio Prep", "Audio Pre-processing")
        _nav_button("Audio Merge", "Audio Merge")

        st.divider()

        _section("View")

        _subject_type_options = ["Transcript", "Group"]

        subject_type_label = st.radio(
            "Type",
            _subject_type_options,
            index=0,
            horizontal=True,
            key="subject_type_selector",
            label_visibility="collapsed",
        )
        subject_type = "transcript" if subject_type_label == "Transcript" else "group"
        st.session_state["subject_type"] = subject_type

        if subject_type == "transcript":
            transcript_options, transcript_format = _get_transcript_dropdown_options()
            if not transcript_options:
                st.caption("No transcripts yet")
                st.session_state["subject_id"] = None
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
                st.session_state["subject_id"] = selected if selected else None
        else:
            try:
                from transcriptx.web.cache_helpers import cached_list_groups

                groups = cached_list_groups()
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
                group_keys = list(group_options.keys())
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
                st.session_state["subject_id"] = (
                    selected_group if selected_group else None
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
                st.session_state["run_id"] = selected_run_id
            else:
                st.caption("No runs yet")
                st.session_state["run_id"] = None
        else:
            st.session_state["run_id"] = None

        _subject_section("Pages")
        _nav_button("Overview", "Overview", key_suffix="_subject")
        _nav_button("Transcript", "Transcript", key_suffix="_subject")
        _nav_button("Charts", "Charts", key_suffix="_subject")
        _nav_button("Insights", "Insights", key_suffix="_subject")
        _nav_button("Data", "Data", key_suffix="_subject")
        _nav_button("Explorer", "File List", key_suffix="_subject")

        _section("Config")
        _nav_button("Settings", "Settings")
        _nav_button("Profiles", "Profiles")
        _nav_button("Diagnostics", "Diagnostics")

    # Main content: show load error if present, then route to page
    if load_error:
        st.error(f"Could not load session list: {load_error}")

    _consume_page_flash()

    current_page = st.session_state.get("page", "Home")
    render_context_bar(st.session_state)

    # Route to appropriate page
    try:
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
        elif current_page == "Transcribe Audio":
            render_transcribe_audio_page()
        elif current_page == "Import Transcript":
            render_upload_transcript_page()
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
            st.info("Speaker pages were removed.")
        elif current_page == "Groups":
            render_groups()
        elif current_page == "Statistics":
            render_statistics()
        elif (
            current_page == "Corrections Studio"
            and _corrections_studio_available
            and render_corrections_studio
        ):
            render_corrections_studio()
        elif current_page == "Speaker Detail":
            st.info("Speaker pages were removed.")
    except Exception as e:
        logger.error(f"Error in main app: {e}", exc_info=True)
        st.error(f"An unexpected error occurred: {e}")
        st.exception(e)


if __name__ == "__main__":
    main()
