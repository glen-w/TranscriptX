"""
Upload Transcript page — upload a transcript file and register it in the app.

Accepts JSON (TranscriptX schema) or other supported formats (e.g. SRT, VTT);
imports to the transcripts directory, registers in the run index, and creates
a minimal run so the transcript appears in Library and subject views.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from collections import Counter
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st

from transcriptx.core.utils.canonicalization import compute_transcript_identity_hash
from transcriptx.core.utils.paths import (
    OUTPUTS_DIR,
    TRANSCRIPTS_IMPORTS_DIR,
)
from transcriptx.core.utils.run_manifest import create_run_manifest, save_run_manifest
from transcriptx.core.utils.slug_manager import register_transcript
from transcriptx.core.utils._path_core import get_canonical_base_name
from transcriptx.core.utils.logger import get_logger
from transcriptx.io.adapters.base import UnsupportedFormatError
from transcriptx.io.import_metadata_sidecar import validate_managed_transcript
from transcriptx.io.managed_import_workflow import run_managed_import_workflow
from transcriptx.web.cache_helpers import clear_transcript_listing_caches
from transcriptx.web.services.recordings_service import RecordingsService
from transcriptx.web.services.rename_service import RenameService

logger = get_logger()

_AUDIO_UPLOAD_TYPES = ["mp3", "wav", "m4a", "flac", "ogg", "aac"]
_IMPORT_TIMEOUT_SECONDS = 120
_KEY_LAST_IMPORTED_TRANSCRIPT_PATH = "import_last_transcript_path"


def _save_uploaded_transcript(uploaded_file: Any) -> tuple[Path, str]:
    """Stage upload under transcripts/imports/; return (staging_path, logical_basename).

    Staging outside ``originals/`` avoids false archive collisions and keeps canonical
    JSON named from the upload basename (see managed import workflow).
    """
    imports_dir = Path(TRANSCRIPTS_IMPORTS_DIR)
    imports_dir.mkdir(parents=True, exist_ok=True)
    logical_basename = Path(getattr(uploaded_file, "name", "uploaded") or "uploaded").name
    dest = imports_dir / f"{uuid.uuid4().hex}_{logical_basename}"
    dest.write_bytes(uploaded_file.read())
    logger.info(
        "Staged uploaded transcript at %s (logical name %s)", dest, logical_basename
    )
    return dest, logical_basename


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
    validation = validate_managed_transcript(transcript_path)
    if not validation.ok:
        raise ValueError(
            f"Transcript is not library-valid managed transcript: {validation.message}"
        )
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


def _build_speaker_map_from_segments(segments: List[Any]) -> Dict[str, str]:
    """Extract stable speaker ID -> original speaker name from imported segments."""
    votes: dict[str, Counter[str]] = {}
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        speaker_id = seg.get("speaker")
        if not isinstance(speaker_id, str) or not speaker_id.strip():
            continue
        original_cue = seg.get("original_cue")
        if not isinstance(original_cue, dict):
            continue
        original_name = original_cue.get("original_speaker")
        if not isinstance(original_name, str) or not original_name.strip():
            continue
        sid = speaker_id.strip()
        name = original_name.strip()
        bucket = votes.setdefault(sid, Counter())
        bucket[name] += 1

    resolved: Dict[str, str] = {}
    for sid, counter in votes.items():
        if not counter:
            continue
        # Deterministic tie-break: most common, then lexical order.
        resolved[sid] = sorted(counter.items(), key=lambda item: (-item[1], item[0]))[
            0
        ][0]
    return resolved


def _persist_imported_speaker_names(transcript_path: Path) -> None:
    """Persist discovered speaker names into sidecar mapping when available."""
    segments = _load_segments_from_json(transcript_path)
    speaker_map = _build_speaker_map_from_segments(segments)
    if not speaker_map:
        return
    from transcriptx.services.speaker_studio.mapping_service import (
        SpeakerMappingService,
    )

    SpeakerMappingService().bulk_update(
        str(transcript_path),
        speaker_map=speaker_map,
        ignored_speakers=[],
        method="batch",
        speaker_map_source={"kind": "imported_original_speaker"},
    )


def _clear_import_caches() -> None:
    """Refresh transcript/session/recording views after import/upload."""
    clear_transcript_listing_caches()
    RecordingsService.list_recordings.clear()  # type: ignore[attr-defined]


def _import_uploaded_transcript(uploaded: Any) -> tuple[str, Path, Path]:
    """Import uploaded transcript and return (session_id, run_dir, transcript_path)."""
    saved_path, logical_basename = _save_uploaded_transcript(uploaded)
    try:
        managed = run_managed_import_workflow(
            saved_path,
            logical_upload_basename=logical_basename,
            overwrite=False,
            delete_staging_on_success=True,
        )
    except UnsupportedFormatError:
        raise
    except ValueError:
        raise

    json_path = managed.json_path

    _persist_imported_speaker_names(json_path)
    slug, run_id, run_dir = _register_uploaded_transcript(json_path)
    return f"{slug}/{run_id}", run_dir, json_path


def _import_uploaded_transcript_with_timeout(
    uploaded: Any,
    timeout_seconds: int = _IMPORT_TIMEOUT_SECONDS,
) -> tuple[str, Path, Path]:
    """Run transcript import with a timeout to avoid endless UI loading."""
    with ThreadPoolExecutor(
        max_workers=1, thread_name_prefix="transcript_import"
    ) as exe:
        future = exe.submit(_import_uploaded_transcript, uploaded)
        try:
            return future.result(timeout=timeout_seconds)
        except FuturesTimeoutError as exc:
            future.cancel()
            raise TimeoutError(
                f"Import timed out after {timeout_seconds}s. "
                "Try a smaller file or a simpler source format."
            ) from exc


def _save_uploaded_recording(uploaded: Any) -> Path:
    """Persist uploaded optional recording to recordings imports location."""
    return RecordingsService.save_uploaded_file(uploaded)


def _render_import_rename_form(transcript_path: Path) -> None:
    if not transcript_path.exists():
        return
    current_name = transcript_path.stem
    st.subheader("Rename imported transcript + linked audio")
    st.caption(
        "Optional. This keeps transcript and linked audio filenames aligned. "
        "Extensions are preserved automatically."
    )
    with st.form("import_rename_form", clear_on_submit=False):
        st.text_input("Current file name", value=current_name, disabled=True)
        target = st.text_input(
            "New file name",
            value=current_name,
            help="Use letters, numbers, spaces, hyphens, and underscores. Do not include extension.",
        )
        submitted = st.form_submit_button("Rename files")
    if not submitted:
        return
    result = RenameService.rename_transcript_and_audio(transcript_path, target)
    if not result.ok:
        st.error(result.message)
        return
    RenameService.refresh_after_rename(result)
    st.session_state[_KEY_LAST_IMPORTED_TRANSCRIPT_PATH] = result.new_transcript_path
    st.success(
        f"Renamed `{result.old_base_name}` to `{result.new_base_name}` "
        "for transcript and linked audio."
    )
    st.rerun()


def render_upload_transcript_page() -> None:
    """Render the Import Transcript page."""
    st.markdown(
        '<div class="main-header">📥 Import Transcript</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Import transcript files into TranscriptX canonical JSON format, and optionally "
        "attach a recording for speaker/audio-feature workflows."
    )

    st.subheader("1. Import transcript")
    with st.form("import_transcript_form", clear_on_submit=False):
        uploaded_transcripts = st.file_uploader(
            "Choose a transcript file",
            type=["json", "srt", "vtt", "txt", "html", "htm"],
            accept_multiple_files=True,
            help="JSON (TranscriptX, Whisper, Sembly), SRT, VTT, HTML (e.g. Sembly export), or other supported formats.",
            key="upload_transcript_file",
        )
        import_submitted = st.form_submit_button(
            "Import Transcript",
            type="primary",
            use_container_width=False,
        )

    if import_submitted:
        if not uploaded_transcripts:
            st.error("Please choose a transcript file to import.")
        else:
            successes: list[tuple[str, Path, Path]] = []
            failures: list[tuple[str, str]] = []
            for uploaded_transcript in uploaded_transcripts:
                try:
                    session_id, run_dir, transcript_path = (
                        _import_uploaded_transcript_with_timeout(uploaded_transcript)
                    )
                except UnsupportedFormatError as e:
                    failures.append(
                        (uploaded_transcript.name, f"Unsupported format: {e}")
                    )
                except ValueError as e:
                    failures.append(
                        (uploaded_transcript.name, f"Invalid transcript: {e}")
                    )
                except TimeoutError as e:
                    failures.append((uploaded_transcript.name, str(e)))
                except Exception as e:
                    logger.exception("Import failed")
                    failures.append((uploaded_transcript.name, f"Import failed: {e}"))
                else:
                    successes.append((session_id, run_dir, transcript_path))

            if successes:
                _clear_import_caches()
                last = successes[-1]
                st.session_state[_KEY_LAST_IMPORTED_TRANSCRIPT_PATH] = str(last[2])
                st.success(f"Imported {len(successes)} transcript(s).")
                for session_id, run_dir, _tp in successes:
                    st.caption(f"Registered as **{session_id}** (`{run_dir}`)")
                st.info(
                    "Select it from **Library** or the **Subject** dropdown to view and run analysis."
                )
            if failures:
                st.error(f"{len(failures)} import(s) failed.")
                for filename, message in failures:
                    st.caption(f"`{filename}`: {message}")

    imported_path = st.session_state.get(_KEY_LAST_IMPORTED_TRANSCRIPT_PATH)
    if imported_path:
        _render_import_rename_form(Path(imported_path))

    st.subheader("2. Optional recording upload")
    st.info(
        "Uploading a recording here does not transcribe audio. "
        "A transcript file is still required for transcript text content. "
        "Optional recordings are used only by speaker identification and audio-derived modules."
    )
    with st.form("optional_recording_upload_form", clear_on_submit=False):
        uploaded_recording = st.file_uploader(
            "Upload recording (optional)",
            type=_AUDIO_UPLOAD_TYPES,
            accept_multiple_files=False,
            help="This stores audio for speaker identification and voice/audio feature modules. It does not generate transcript text.",
            key="upload_optional_recording_file",
        )
        recording_submitted = st.form_submit_button("Upload Recording")

    if recording_submitted:
        if not uploaded_recording:
            st.info("No recording selected. Transcript import works without audio.")
        else:
            try:
                saved_recording = _save_uploaded_recording(uploaded_recording)
            except Exception as e:
                logger.exception("Recording upload failed")
                st.error(f"Recording upload failed: {e}")
            else:
                _clear_import_caches()
                st.success(f"Saved recording to `{saved_recording}`.")
                st.caption(
                    "This recording is available for speaker identification and audio-derived features."
                )
