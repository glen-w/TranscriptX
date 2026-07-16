"""
Home / Dashboard page for TranscriptX.
"""

from __future__ import annotations

import hashlib
import html
from pathlib import Path

import pandas as pd
import streamlit as st

from transcriptx.utils.text_utils import format_duration_display_from_config
from transcriptx.web.cache_helpers import cached_list_recent_runs
from transcriptx.web.components.action_links import render_action_link
from transcriptx.web.components.empty_state import render_empty_state
from transcriptx.web.components.page_shell import render_page_shell
from transcriptx.web.components.run_id_info import build_run_id_info_html
from transcriptx.web.context_format import (
    format_run_display,
    friendly_subject_label,
)
from transcriptx.web.navigation import navigate_to_library_rename_workflow
from transcriptx.web.perf import instrument_cached_call, set_count
from transcriptx.web.services.artifact_service import ArtifactService
from transcriptx.web.services.export_service import ExportService
from transcriptx.web.services.file_service import FileService
from transcriptx.web.sidebar_options import _slug_display_labels_from_index
from transcriptx.web.state import PAGE_KEY, apply_subject_context
from transcriptx.web.utils import (
    get_all_sessions_statistics,
    list_available_sessions,
)

_HOME_EXPORT_ERROR_PREFIX = "home_export_error_"


@st.cache_data(ttl=60, show_spinner=False)
def _cached_sessions_and_stats() -> tuple[list, dict]:
    sessions = list_available_sessions()
    stats = get_all_sessions_statistics()
    return sessions, stats


def _transcript_path_for_recent_run(run) -> Path | None:
    slug = run.run_dir.parent.name
    resolved = FileService.resolve_transcript_path(f"{slug}/{run.run_dir.name}")
    if resolved is not None:
        return resolved
    tp = run.transcript_path
    if tp and str(tp) and not str(tp).startswith("sha256:"):
        candidate = Path(tp)
        if candidate.exists():
            return candidate
    return None


def _home_export_session_key(run_id: str) -> str:
    return f"home_export_zip_{run_id}"


def _home_export_error_key(run_id: str) -> str:
    return f"{_HOME_EXPORT_ERROR_PREFIX}{run_id}"


def _row_key_suffix(run_id: str, row_index: int) -> str:
    digest = hashlib.sha1(f"{row_index}:{run_id}".encode("utf-8")).hexdigest()[:12]
    return f"{row_index}_{digest}"


def _prepare_recent_run_export(run) -> None:
    """Build a full-run artifact ZIP and stash bytes for download."""
    export_key = _home_export_session_key(run.run_id)
    error_key = _home_export_error_key(run.run_id)
    try:
        artifacts = ArtifactService.list_artifacts(run.run_dir)
        if not artifacts:
            st.session_state.pop(export_key, None)
            st.session_state[error_key] = "No artifacts to export for this run."
            return
        export_path = ExportService.zip_artifacts(
            run.run_dir, [artifact.id for artifact in artifacts]
        )
        if export_path is None:
            st.session_state.pop(export_key, None)
            st.session_state[error_key] = "Export failed."
            return
        st.session_state.pop(error_key, None)
        st.session_state[export_key] = {
            "bytes": ArtifactService.read_for_download(export_path),
            "filename": export_path.name,
        }
    except ValueError as exc:
        st.session_state.pop(export_key, None)
        st.session_state[error_key] = str(exc)
    except Exception as exc:
        st.session_state.pop(export_key, None)
        st.session_state[error_key] = f"Export failed: {exc}"


def _render_recent_run_export_download(run_id: str, *, key_suffix: str) -> None:
    stored = st.session_state.get(_home_export_session_key(run_id))
    if not isinstance(stored, dict):
        return
    payload = stored.get("bytes")
    filename = stored.get("filename")
    if not isinstance(payload, (bytes, bytearray)) or not isinstance(filename, str):
        return
    st.download_button(
        "Download ZIP",
        data=bytes(payload),
        file_name=filename,
        mime="application/zip",
        key=f"home_run_dl_{key_suffix}",
    )


def _render_transcript_overview() -> bool:
    """Render unique-transcript metrics. Returns True when sessions exist."""
    sessions, stats = _cached_sessions_and_stats()
    if not sessions:
        st.info("No transcripts found. Process transcripts to see statistics here.")
        return False

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.metric(
            "Transcripts",
            stats.get("total_transcripts", stats.get("total_sessions", 0)),
        )
    with col2:
        st.metric("Sessions", stats.get("total_sessions", len(sessions)))
    with col3:
        st.metric(
            "Total duration",
            format_duration_display_from_config(stats.get("total_duration_seconds", 0)),
            help="Sum of unique transcript durations",
        )
    with col4:
        st.metric("Total words", f"{stats.get('total_word_count', 0):,}")
    with col5:
        st.metric("Speakers (max)", stats.get("total_speakers", 0))
    with col6:
        st.metric(
            "Analysis completion",
            f"{stats.get('average_completion', 0):.0f}%",
            help="Average analysis completion across unique transcripts",
        )
    return True


def _render_sessions_table() -> None:
    """Render the per-session table in a collapsible section."""
    sessions, _stats = _cached_sessions_and_stats()
    if not sessions:
        return

    with st.expander("sessions", expanded=False):
        rows = []
        for s in sorted(
            sessions,
            key=lambda session: session.get("duration_seconds", 0),
            reverse=True,
        ):
            rows.append(
                {
                    "Session": s.get("name", ""),
                    "Duration": format_duration_display_from_config(
                        s.get("duration_seconds", 0)
                    ),
                    "Words": s.get("word_count", 0),
                    "Segments": s.get("segment_count", 0),
                    "Speakers": s.get("speaker_count", 0),
                    "Completion %": s.get("analysis_completion", 0),
                }
            )
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def _navigate_recent_run(run, *, page: str) -> None:
    apply_subject_context(
        st.session_state,
        subject_type="transcript",
        subject_id=run.run_dir.parent.name,
        run_id=run.run_dir.name,
    )
    st.session_state[PAGE_KEY] = page


def _recent_run_meta_parts(run) -> list[str]:
    parts: list[str] = []
    status = getattr(run, "status", None)
    if status and str(status).strip() and str(status).strip().lower() != "unknown":
        parts.append(str(status).strip())
    duration = getattr(run, "duration_seconds", None)
    if duration is not None:
        try:
            label = format_duration_display_from_config(duration)
            if label and label.strip() and label.strip() != "—":
                parts.append(label.strip())
        except Exception:
            pass
    modules = getattr(run, "selected_modules", None) or []
    if modules:
        parts.append(f"{len(modules)} modules")
    profile = getattr(run, "profile_name", None)
    if profile and str(profile).strip():
        parts.append(str(profile).strip())
    return parts


def _render_recent_run_row(run, *, row_index: int, slug_labels: dict[str, str]) -> None:
    slug = run.run_dir.parent.name
    stem = (
        run.transcript_path.stem
        if run.transcript_path and run.transcript_path.name
        else None
    )
    title = friendly_subject_label(
        "transcript",
        subject_id=slug,
        slug_labels=slug_labels,
        stem=stem,
    )
    run_display = format_run_display(
        run.run_id,
        fallback_dt=getattr(run, "created_at", None),
        allow_raw_fallback=False,
    )
    meta_parts = _recent_run_meta_parts(run)
    meta_line = " · ".join(meta_parts) if meta_parts else ""
    key_suffix = _row_key_suffix(run.run_id, row_index)
    info_html = ""
    if run.run_id:
        info_html = " " + build_run_id_info_html(
            run.run_id, control_id=f"tx-home-run-tip-{key_suffix}"
        )

    secondary = ""
    tp = getattr(run, "transcript_path", None)
    if tp and str(tp) and not str(tp).startswith("sha256:"):
        secondary = f"Transcript: {html.escape(str(tp))}"

    st.markdown(
        f'<div class="tx-recent-run-row" data-testid="tx-recent-run-row-{key_suffix}">'
        f'<div class="tx-recent-run-title">{html.escape(title)}'
        f'<span class="tx-recent-run-when"> · {html.escape(run_display)}</span>'
        f"{info_html}</div>"
        + (
            f'<div class="tx-recent-run-meta">{html.escape(meta_line)}</div>'
            if meta_line
            else ""
        )
        + (
            f'<div class="tx-recent-run-secondary">{secondary}</div>'
            if secondary
            else ""
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    def _rename_cb(r=run) -> None:
        transcript_path = _transcript_path_for_recent_run(r)
        if transcript_path is not None:
            navigate_to_library_rename_workflow(st.session_state, transcript_path)
        else:
            st.session_state[PAGE_KEY] = "Library"

    # Compact text-link row: Open | Charts | Artifacts | Export ZIP | Rename
    action_cols = st.columns(5, gap="small")
    with action_cols[0]:
        render_action_link(
            "Open",
            key=f"home_run_ov_{key_suffix}",
            icon=":material/folder_open:",
            on_click=_navigate_recent_run,
            args=(run,),
            kwargs={"page": "Overview"},
        )
    with action_cols[1]:
        render_action_link(
            "Charts",
            key=f"home_run_ch_{key_suffix}",
            icon=":material/bar_chart:",
            on_click=_navigate_recent_run,
            args=(run,),
            kwargs={"page": "Charts"},
        )
    with action_cols[2]:
        render_action_link(
            "Artifacts",
            key=f"home_run_dt_{key_suffix}",
            icon=":material/inventory_2:",
            on_click=_navigate_recent_run,
            args=(run,),
            kwargs={"page": "Artifacts"},
        )
    with action_cols[3]:
        if render_action_link(
            "Export ZIP",
            key=f"home_run_ex_{key_suffix}",
            icon=":material/folder_zip:",
        ):
            _prepare_recent_run_export(run)
    with action_cols[4]:
        render_action_link(
            "Rename",
            key=f"home_run_rn_{key_suffix}",
            icon=":material/drive_file_rename_outline:",
            on_click=_rename_cb,
        )

    error_msg = st.session_state.get(_home_export_error_key(run.run_id))
    if error_msg:
        st.warning(str(error_msg))
    _render_recent_run_export_download(run.run_id, key_suffix=key_suffix)


def render_home() -> None:
    """Render the home/dashboard page."""
    render_page_shell("Home")

    try:
        if _render_transcript_overview():
            _render_sessions_table()

        runs = instrument_cached_call(
            "cached_list_recent_runs",
            cached_list_recent_runs,
            limit=10,
            bucket="home_summary",
        )
        set_count("recent_runs_returned", len(runs))

        with st.expander("Recent runs", expanded=False):
            if not runs:
                render_empty_state(
                    "no_results_yet",
                    "No analysis runs yet",
                    "Start from the Library or Run Analysis after adding transcripts.",
                    primary_action=("Run Analysis", "Run Analysis"),
                    secondary_action=("Library", "Library"),
                )
            else:
                slug_labels = _slug_display_labels_from_index()
                for idx, run in enumerate(runs[:5]):
                    _render_recent_run_row(run, row_index=idx, slug_labels=slug_labels)
    except Exception as e:
        st.error(f"Could not load dashboard: {e}")
