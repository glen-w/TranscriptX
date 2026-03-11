"""
Upload Transcript page — upload a transcript file and register it in the app.

Accepts JSON (TranscriptX schema) or other supported formats (e.g. SRT, VTT);
imports to the transcripts directory, registers in the run index, and creates
a minimal run so the transcript appears in Library and subject views.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, List

import streamlit as st

from transcriptx.core.utils.canonicalization import compute_transcript_identity_hash
from transcriptx.core.utils.paths import DIARISED_TRANSCRIPTS_DIR, OUTPUTS_DIR
from transcriptx.core.utils.run_manifest import create_run_manifest, save_run_manifest
from transcriptx.core.utils.slug_manager import register_transcript
from transcriptx.core.utils._path_core import get_canonical_base_name
from transcriptx.core.utils.logger import get_logger

logger = get_logger()

_IMPORTS_SUBDIR = "imports"


def _save_uploaded_transcript(uploaded_file: Any, transcripts_dir: Path) -> Path:
    """Save Streamlit UploadedFile to transcripts_dir/imports/<name>. Creates dirs if needed."""
    imports_dir = transcripts_dir / _IMPORTS_SUBDIR
    imports_dir.mkdir(parents=True, exist_ok=True)
    name = getattr(uploaded_file, "name", "uploaded")
    dest = imports_dir / name
    dest.write_bytes(uploaded_file.read())
    logger.info(f"Saved uploaded transcript to {dest}")
    return dest


def _load_segments_from_json(transcript_path: Path) -> List[Any]:
    """Load segments from a TranscriptX JSON file. Raises if invalid."""
    import json

    with open(transcript_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    segments = data.get("segments")
    if not segments or not isinstance(segments, list):
        raise ValueError("No segments found in transcript")
    return segments


def _register_uploaded_transcript(transcript_path: Path) -> tuple[str, str, Path]:
    """
    Register transcript in the index and create a minimal run so it appears in the app.

    Returns:
        (slug, run_id, run_dir)
    """
    segments = _load_segments_from_json(transcript_path)
    transcript_key = compute_transcript_identity_hash(segments)
    run_id = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    source_basename = get_canonical_base_name(str(transcript_path))

    slug = register_transcript(
        transcript_key=transcript_key,
        transcript_path=str(transcript_path),
        run_id=run_id,
        source_basename=source_basename,
        source_path=str(transcript_path),
    )

    run_dir = Path(OUTPUTS_DIR) / slug / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest = create_run_manifest(
        transcript_path=str(transcript_path.resolve()),
        transcript_identity_hash=transcript_key,
        run_id=run_id,
        source_basename=source_basename,
        source_path=str(transcript_path.resolve()),
    )
    save_run_manifest(manifest, str(run_dir))

    return slug, run_id, run_dir


def render_upload_transcript_page() -> None:
    """Render the Upload Transcript page."""
    st.markdown(
        '<div class="main-header">📤 Upload Transcript</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Upload a transcript file to add it to your library. "
        "Supports TranscriptX JSON and other formats (e.g. SRT, VTT, Whisper-style JSON) — "
        "they will be converted to the standard schema."
    )

    uploaded = st.file_uploader(
        "Choose a transcript file",
        type=["json", "srt", "vtt", "txt", "html", "htm"],
        accept_multiple_files=False,
        help="JSON (TranscriptX, Whisper, Sembly), SRT, VTT, HTML (e.g. Sembly export), or other supported formats.",
        key="upload_transcript_file",
    )

    if not uploaded:
        st.info("Select a file above to upload.")
        return

    # Save to imports then import to transcripts dir
    try:
        saved_path = _save_uploaded_transcript(uploaded, DIARISED_TRANSCRIPTS_DIR)
    except Exception as e:
        logger.exception("Failed to save uploaded file")
        st.error(f"Failed to save file: {e}")
        return

    # Convert to standard JSON if needed
    try:
        from transcriptx.io.transcript_importer import import_transcript
        from transcriptx.io.adapters.base import UnsupportedFormatError

        try:
            json_path = import_transcript(
                saved_path,
                output_dir=DIARISED_TRANSCRIPTS_DIR,
                overwrite=True,
            )
        except UnsupportedFormatError as e:
            st.error(f"Unsupported format: {e}")
            return
        except ValueError as e:
            st.error(f"Invalid transcript: {e}")
            return
    except Exception as e:
        logger.exception("Import failed")
        st.error(f"Import failed: {e}")
        return

    # Register and create run
    try:
        slug, run_id, run_dir = _register_uploaded_transcript(json_path)
    except ValueError as e:
        st.error(str(e))
        return
    except Exception as e:
        logger.exception("Registration failed")
        st.error(f"Registration failed: {e}")
        return

    session_id = f"{slug}/{run_id}"
    st.success(f"Transcript registered as **{session_id}**.")
    st.caption(f"Run directory: `{run_dir}`")
    st.info(
        "Select it from **Library** or the **Subject** dropdown to view and run analysis."
    )
