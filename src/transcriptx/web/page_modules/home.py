"""
Home / Dashboard page for TranscriptX.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from transcriptx.core.utils.paths import OUTPUTS_DIR
from transcriptx.web.cache_helpers import (
    cached_list_groups,
    cached_list_recent_runs,
    get_cached_list_transcripts,
)
from transcriptx.web.components.empty_state import render_empty_state
from transcriptx.web.components.page_shell import render_page_help, render_page_shell
from transcriptx.web.navigation import navigate_to_library_rename_workflow
from transcriptx.web.perf import instrument_cached_call, set_count
from transcriptx.web.services.artifact_service import ArtifactService
from transcriptx.web.services.export_service import ExportService
from transcriptx.web.services.file_service import FileService
from transcriptx.web.sidebar_options import _slug_display_labels_from_index

_HOME_HELP = "**Home** is the landing page. Use the header actions or **Recent Runs** to open analysis."
_HOME_WORKSPACE_SUMMARY_REQUESTED = "home_workspace_summary_requested"


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


def _prepare_recent_run_export(run) -> None:
    """Build a full-run artifact ZIP and stash bytes for download."""
    export_key = _home_export_session_key(run.run_id)
    try:
        artifacts = ArtifactService.list_artifacts(run.run_dir)
        if not artifacts:
            st.session_state.pop(export_key, None)
            st.warning("No artifacts to export for this run.")
            return
        export_path = ExportService.zip_artifacts(
            run.run_dir, [artifact.id for artifact in artifacts]
        )
        if export_path is None:
            st.session_state.pop(export_key, None)
            st.warning("Export failed.")
            return
        st.session_state[export_key] = {
            "bytes": ArtifactService.read_for_download(export_path),
            "filename": export_path.name,
        }
    except ValueError as exc:
        st.session_state.pop(export_key, None)
        st.error(str(exc))
    except Exception as exc:
        st.session_state.pop(export_key, None)
        st.error(f"Export failed: {exc}")


def _render_recent_run_export_download(run_id: str) -> None:
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
        key=f"home_run_dl_{run_id}",
    )


def render_home() -> None:
    """Render the home/dashboard page."""
    render_page_shell(
        "Home",
        "Launchpad for recent activity and analysis workflows.",
        badges=None,
        actions=[("Library", "Library"), ("Run Analysis", "Run Analysis")],
    )

    try:
        runs = instrument_cached_call(
            "cached_list_recent_runs",
            cached_list_recent_runs,
            limit=10,
            bucket="home_summary",
        )
        set_count("recent_runs_returned", len(runs))

        last_run_label = "—"
        if runs:
            last_run_label = runs[0].created_at.strftime("%Y-%m-%d %H:%M")

        st.subheader("Recent Activity")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(
                '<div class="stat-card"><strong>Recent runs</strong><br/>'
                f"<span style='font-size:1.4rem'>{len(runs)}</span></div>",
                unsafe_allow_html=True,
            )
        with col2:
            st.markdown(
                '<div class="stat-card"><strong>Last run</strong><br/>'
                f"<span style='font-size:0.95rem'>{last_run_label}</span></div>",
                unsafe_allow_html=True,
            )
        with col3:
            st.markdown(
                '<div class="stat-card"><strong>Output root</strong><br/>'
                f"<span style='font-size:0.95rem'>{'OK' if Path(OUTPUTS_DIR).exists() else 'N/A'}</span></div>",
                unsafe_allow_html=True,
            )

        st.divider()
        st.subheader("Recent Runs")
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
            for run in runs[:5]:
                slug = run.run_dir.parent.name
                transcript_name = slug_labels.get(slug) or (
                    run.transcript_path.stem
                    if run.transcript_path and run.transcript_path.name
                    else slug
                )
                with st.expander(
                    f"{transcript_name} — {run.run_id} — "
                    f"{run.created_at.strftime('%Y-%m-%d %H:%M')}"
                ):
                    st.caption(f"Transcript: {run.transcript_path}")
                    st.caption(
                        f"Modules: {', '.join(run.selected_modules[:5])}{'...' if len(run.selected_modules) > 5 else ''}"
                    )
                    c1, c2, c3, c4, c5 = st.columns(5)
                    with c1:
                        if st.button("Overview", key=f"home_run_ov_{run.run_id}"):
                            st.session_state["subject_type"] = "transcript"
                            st.session_state["subject_id"] = run.run_dir.parent.name
                            st.session_state["run_id"] = run.run_dir.name
                            st.session_state["page"] = "Overview"
                            st.rerun()
                    with c2:
                        if st.button("Charts", key=f"home_run_ch_{run.run_id}"):
                            st.session_state["subject_type"] = "transcript"
                            st.session_state["subject_id"] = run.run_dir.parent.name
                            st.session_state["run_id"] = run.run_dir.name
                            st.session_state["page"] = "Charts"
                            st.rerun()
                    with c3:
                        if st.button("Artifacts", key=f"home_run_dt_{run.run_id}"):
                            st.session_state["subject_type"] = "transcript"
                            st.session_state["subject_id"] = run.run_dir.parent.name
                            st.session_state["run_id"] = run.run_dir.name
                            st.session_state["page"] = "Artifacts"
                            st.rerun()
                    with c4:
                        if st.button("Export ZIP", key=f"home_run_ex_{run.run_id}"):
                            _prepare_recent_run_export(run)
                    with c5:
                        if st.button("Rename", key=f"home_run_rn_{run.run_id}"):
                            transcript_path = _transcript_path_for_recent_run(run)
                            if transcript_path is not None:
                                navigate_to_library_rename_workflow(
                                    st.session_state, transcript_path
                                )
                            else:
                                st.session_state["page"] = "Library"
                            st.rerun()
                    _render_recent_run_export_download(run.run_id)

        st.subheader("Workspace Summary")
        if not st.session_state.get(_HOME_WORKSPACE_SUMMARY_REQUESTED, False):
            st.caption("Load workspace summary when you need group-level counts.")
            if st.button(
                "Load workspace summary",
                key="home_load_workspace_summary",
                width="stretch",
            ):
                st.session_state[_HOME_WORKSPACE_SUMMARY_REQUESTED] = True
                st.rerun()
        else:
            groups = instrument_cached_call(
                "cached_list_groups",
                cached_list_groups,
                bucket="home_summary",
            )
            transcripts = instrument_cached_call(
                "get_cached_list_transcripts",
                get_cached_list_transcripts,
                bucket="home_summary",
            )
            set_count("groups_returned", len(groups))
            set_count("transcripts_returned", len(transcripts))
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(
                    '<div class="stat-card"><strong>Groups</strong><br/>'
                    f"<span style='font-size:1.4rem'>{len(groups)}</span></div>",
                    unsafe_allow_html=True,
                )
            with col2:
                st.markdown(
                    '<div class="stat-card"><strong>Transcripts</strong><br/>'
                    f"<span style='font-size:1.4rem'>{len(transcripts)}</span></div>",
                    unsafe_allow_html=True,
                )

        render_page_help(_HOME_HELP)
    except Exception as e:
        st.error(f"Could not load dashboard: {e}")
        render_page_help(_HOME_HELP)
