"""Shared helpers for System → Tools audio panels."""

from __future__ import annotations

from pathlib import Path
from typing import List

import streamlit as st

from transcriptx.core.audio.tools import PYDUB_AVAILABLE, check_ffmpeg_available
from transcriptx.core.utils.paths import RECORDINGS_DIR, RECORDINGS_IMPORTS_DIR
from transcriptx.web.services.recordings_service import RecordingsService
from transcriptx.web.components.info_tooltip import widget_help

_AUDIO_UPLOAD_TYPES = ["mp3", "wav", "m4a", "flac", "ogg", "aac"]


def recordings_path_label(path: Path) -> str:
    """Label relative to recordings root when possible."""
    try:
        return str(path.relative_to(RECORDINGS_DIR))
    except ValueError:
        return path.name


def list_available_recordings() -> List[Path]:
    """List recordings under RECORDINGS_DIR plus imports when that root differs."""
    recordings = list(RecordingsService.list_recordings(RECORDINGS_DIR))
    if RECORDINGS_IMPORTS_DIR != RECORDINGS_DIR / "imports":
        seen = {p.resolve() for p in recordings}
        for path in RecordingsService.list_recordings(RECORDINGS_IMPORTS_DIR):
            if path.resolve() not in seen:
                recordings.append(path)
        recordings.sort(key=lambda p: p.name)
    return recordings


def tools_deps_ready() -> tuple[bool, list[str]]:
    """Return whether merge/preprocess can run, plus human-readable missing deps."""
    missing: list[str] = []
    ffmpeg_ok, ffmpeg_err = check_ffmpeg_available()
    if not ffmpeg_ok:
        missing.append(ffmpeg_err or "ffmpeg is not available")
    if not PYDUB_AVAILABLE:
        missing.append("pydub is not installed (pip install pydub)")
    return not missing, missing


def render_dependency_banner() -> bool:
    """Show dependency status; return True when tools can run."""
    ready, missing = tools_deps_ready()
    if ready:
        st.caption("Dependencies: ffmpeg and pydub are available.")
        return True
    st.error(
        "Audio tools need **ffmpeg** and **pydub** on the host. "
        + " · ".join(missing)
    )
    st.caption(
        "Install ffmpeg on the host and ensure pydub is in the Python environment, "
        "then reload this page. CLI fallbacks: `scripts/audio_preprocess.py`, "
        "`scripts/audio_merge.py`."
    )
    return False


def render_upload_and_refresh(
    *,
    uploader_key: str,
    selected_files_key: str | None = None,
) -> List[Path]:
    """
    Render upload control, persist files, and return the refreshed recordings list.

    When *selected_files_key* is set, newly uploaded paths are written there so
    the caller can auto-select them.
    """
    uploaded_list = st.file_uploader(
        "Upload audio file(s)",
        type=_AUDIO_UPLOAD_TYPES,
        accept_multiple_files=True,
        help=widget_help((
            "Uploaded files are saved to the recordings imports folder and appear "
            "in the list below. Limit 500 MB per file when STREAMLIT_SERVER_MAX_UPLOAD_SIZE=500."
        )),
        key=uploader_key,
    )
    if uploaded_list:
        saved_paths: List[Path] = []
        save_errors: List[str] = []
        for uploaded in uploaded_list:
            try:
                saved_paths.append(RecordingsService.save_uploaded_file(uploaded))
            except Exception as exc:
                save_errors.append(f"{uploaded.name}: {exc}")
        if save_errors:
            for err in save_errors:
                st.error(err)
            st.caption(
                "If you see **AxiosError: Network Error** in the uploader, the upload "
                "often failed due to size limit, timeout, or proxy. When using Docker, "
                "ensure the server allows 500 MB (STREAMLIT_SERVER_MAX_UPLOAD_SIZE=500)."
            )
        if saved_paths:
            if len(saved_paths) == 1:
                try:
                    rel = saved_paths[0].relative_to(RECORDINGS_IMPORTS_DIR)
                except ValueError:
                    rel = saved_paths[0].name
                st.success(f"Saved to `{rel}`")
            else:
                st.success(
                    f"Saved {len(saved_paths)} files to `{RECORDINGS_IMPORTS_DIR.name}/`"
                )
            RecordingsService.list_recordings.clear()  # type: ignore[attr-defined]
            if selected_files_key is not None:
                st.session_state[selected_files_key] = [str(p) for p in saved_paths]

    return list_available_recordings()


def render_empty_recordings_hint() -> None:
    st.info(
        f"No audio files found in `{RECORDINGS_DIR}`. "
        "Upload a file above or add files to the recordings directory."
    )
