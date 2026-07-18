"""Navigation and export helpers for action menus (no recent_run_row imports)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from transcriptx.web.action_menus.context import CanonicalIdentity
from transcriptx.web.navigation import (
    make_session_path_resolver,
    navigate_to_library_rename_workflow,
)
from transcriptx.web.services.artifact_service import ArtifactService
from transcriptx.web.services.export_service import ExportService
from transcriptx.web.services.file_service import FileService
from transcriptx.web.services.subject_service import SubjectService
from transcriptx.web.state import PAGE_KEY, apply_subject_context

# Page destinations from navigation registry keys (single source of truth).
PAGE_OVERVIEW = "Overview"
PAGE_CHARTS = "Charts"
PAGE_ARTIFACTS = "Artifacts"
PAGE_INSIGHTS = "Insights"
PAGE_TRANSCRIPT = "Transcript"
PAGE_LIBRARY = "Library"
PAGE_SPEAKER_ID = "Speaker ID"
PAGE_RUN_ANALYSIS = "Run Analysis"
PAGE_CORRECTIONS = "Corrections Studio"


def apply_identity_to_session(
    session_state: dict[str, Any], identity: CanonicalIdentity
) -> None:
    """Write validated identity into session before page navigation."""
    apply_subject_context(
        session_state,
        subject_type=identity.subject_type,  # type: ignore[arg-type]
        subject_id=identity.subject_id,
        run_id=identity.run_id,
    )
    if (
        identity.subject_type == "transcript"
        and identity.transcript_path is not None
        and identity.run_id is None
    ):
        SubjectService.set_transcript_context_from_path(
            session_state,
            identity.transcript_path,
            session_resolver=make_session_path_resolver(),
        )
        # Preserve explicit run absence after path hydration when no run.
        if identity.run_id is None:
            apply_subject_context(
                session_state,
                subject_type="transcript",
                subject_id=identity.subject_id,
                run_id=None,
            )


def navigate_with_identity(
    identity: CanonicalIdentity, page: str, session_state: dict[str, Any] | None = None
) -> None:
    ss = session_state if session_state is not None else st.session_state
    apply_identity_to_session(ss, identity)
    ss[PAGE_KEY] = page


def transcript_path_for_run(run) -> Path | None:
    slug = run.run_dir.parent.name
    resolved = FileService.resolve_transcript_path(f"{slug}/{run.run_dir.name}")
    if resolved is not None:
        return resolved
    tp = getattr(run, "transcript_path", None)
    if tp and str(tp) and not str(tp).startswith("sha256:"):
        candidate = Path(tp)
        if candidate.exists():
            return candidate
    return None


def export_payload_key(identity: CanonicalIdentity) -> str:
    return f"action_menu_export_zip_{identity.export_key_suffix}"


def export_error_key(identity: CanonicalIdentity) -> str:
    return f"action_menu_export_error_{identity.export_key_suffix}"


def prepare_run_export(identity: CanonicalIdentity) -> None:
    """Build a full-run artifact ZIP keyed by subject+run."""
    export_key = export_payload_key(identity)
    error_key = export_error_key(identity)
    run_dir = identity.run_dir
    if run_dir is None:
        st.session_state.pop(export_key, None)
        st.session_state[error_key] = "No run directory for export."
        return
    try:
        artifacts = ArtifactService.list_artifacts(run_dir)
        if not artifacts:
            st.session_state.pop(export_key, None)
            st.session_state[error_key] = "No artifacts to export for this run."
            return
        export_path = ExportService.zip_artifacts(
            run_dir, [artifact.id for artifact in artifacts]
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


def render_export_residuals(
    identity: CanonicalIdentity, *, download_key: str
) -> None:
    error_msg = st.session_state.get(export_error_key(identity))
    if error_msg:
        st.warning(str(error_msg))
    stored = st.session_state.get(export_payload_key(identity))
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
        key=download_key,
    )


def go_rename(identity: CanonicalIdentity) -> None:
    if identity.transcript_path is not None:
        navigate_to_library_rename_workflow(st.session_state, identity.transcript_path)
    else:
        st.session_state[PAGE_KEY] = PAGE_LIBRARY
