"""
Upload Transcript page — upload a transcript file and register it in the app.

Accepts JSON (TranscriptX schema) or other supported formats (e.g. SRT, VTT);
imports to the transcripts directory, registers in the run index, and creates
a minimal run so the transcript appears in Library and subject views.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import streamlit as st

from transcriptx.core.utils.paths import TRANSCRIPTS_IMPORTS_DIR
from transcriptx.core.utils.logger import get_logger
from transcriptx.io.admit_and_register import (
    AdmitOutcomeKind,
    admit_and_register,
)
from transcriptx.io.folder_import import (
    ScanHandle,
    eligible_candidates,
    import_folder_candidates,
    is_eligible_status,
    scan_folder_for_import,
    scan_handle_still_valid,
    status_help,
    status_label,
)
from transcriptx.io.import_admission import (
    SUPPORTED_IMPORT_UPLOAD_TYPES,
    sanitize_upload_basename,
)
from transcriptx.io.managed_import_workflow import StagingCleanupPolicy
from transcriptx.web.cache_helpers import clear_transcript_listing_caches
from transcriptx.web.action_menus.context import ActionContext, build_canonical_identity
from transcriptx.web.action_menus.ids import NavStyle, SectionId
from transcriptx.web.action_menus.render import render_configured_actions
from transcriptx.web.components.rename_form import render_transcript_rename_form
from transcriptx.web.services.recordings_service import RecordingsService

logger = get_logger()

_AUDIO_UPLOAD_TYPES = ["mp3", "wav", "m4a", "flac", "ogg", "aac"]
_KEY_LAST_IMPORTED_TRANSCRIPT_PATH = "import_last_transcript_path"
_KEY_FOLDER_PATH = "import_folder_path_input"
_KEY_SCAN_HANDLE = "import_folder_scan_handle"
_KEY_SCAN_BANNER = "import_folder_scan_banner"


def _save_uploaded_transcript(uploaded_file: Any) -> tuple[Path, str]:
    """Stage upload under transcripts/imports/; return (staging_path, logical_basename)."""
    imports_dir = Path(TRANSCRIPTS_IMPORTS_DIR)
    imports_dir.mkdir(parents=True, exist_ok=True)
    logical_basename = sanitize_upload_basename(
        getattr(uploaded_file, "name", "uploaded") or "uploaded"
    )
    dest = imports_dir / f"{uuid.uuid4().hex}_{logical_basename}"
    dest.write_bytes(uploaded_file.read())
    logger.info(
        "Staged uploaded transcript at %s (logical name %s)", dest, logical_basename
    )
    return dest, logical_basename


def _clear_import_caches() -> None:
    """Refresh transcript/session/recording views after import/upload."""
    clear_transcript_listing_caches()
    RecordingsService.list_recordings.clear()  # type: ignore[attr-defined]


def _import_uploaded_transcript(uploaded: Any) -> AdmitOutcomeKind:
    """Admit uploaded transcript via shared admit_and_register."""
    saved_path, logical_basename = _save_uploaded_transcript(uploaded)
    outcome = admit_and_register(
        saved_path,
        logical_basename=logical_basename,
        staging_cleanup=StagingCleanupPolicy.APP_IMPORTS_ONLY,
        allow_provenance_backfill=True,
    )
    if outcome.artifact_committed or outcome.registration_progressed:
        _clear_import_caches()
    if outcome.transcript_path is not None and outcome.kind in {
        AdmitOutcomeKind.IMPORTED_AND_REGISTERED,
        AdmitOutcomeKind.PARTIAL_STATE_REPAIRED,
        AdmitOutcomeKind.REGISTRATION_RECOVERED,
    }:
        st.session_state[_KEY_LAST_IMPORTED_TRANSCRIPT_PATH] = str(
            outcome.transcript_path
        )
    if outcome.kind in {
        AdmitOutcomeKind.IMPORTED_AND_REGISTERED,
        AdmitOutcomeKind.PARTIAL_STATE_REPAIRED,
        AdmitOutcomeKind.REGISTRATION_RECOVERED,
        AdmitOutcomeKind.ALREADY_MANAGED,
    }:
        return outcome.kind
    raise RuntimeError(outcome.user_safe_detail)


def _render_post_import_actions(transcript_path: Path) -> None:
    """Icon-link strip for next steps after a successful import."""
    identity = build_canonical_identity(
        subject_type="transcript",
        subject_id=transcript_path.stem,
        transcript_path=transcript_path,
    )
    ctx = ActionContext(
        identity=identity,
        widget_identity=f"import_{transcript_path.stem}",
        nav_style=NavStyle.ON_CLICK,
        instance_prefix="import",
        rename_supported=True,
    )
    render_configured_actions(SectionId.IMPORT_SUCCESS, ctx)


def _smart_rename_mode() -> str:
    try:
        from transcriptx.core.utils.config_provider import get_config

        cfg = get_config()
        return str(
            getattr(getattr(cfg, "input", None), "smart_rename_mode", "suggest_import")
            or "suggest_import"
        )
    except Exception:
        return "suggest_import"


def _smart_rename_pattern() -> str:
    try:
        from transcriptx.core.utils.config_provider import get_config

        cfg = get_config()
        return str(
            getattr(
                getattr(cfg, "input", None),
                "smart_rename_pattern",
                "{yymmdd}_{period}_{n}",
            )
            or "{yymmdd}_{period}_{n}"
        )
    except Exception:
        return "{yymmdd}_{period}_{n}"


def _maybe_auto_rename_imported(transcript_path: Path) -> Path:
    """When mode is auto_import, rename using the smart pattern. Returns current path."""
    from transcriptx.core.utils.rename.smart_name import (
        smart_rename_auto_on_import,
        suggest_smart_rename_base_name,
    )
    from transcriptx.web.services.rename_service import RenameService

    mode = _smart_rename_mode()
    if not smart_rename_auto_on_import(mode):
        return transcript_path

    processed_key = "import_auto_rename_processed_path"
    current_key = str(transcript_path)
    if st.session_state.get(processed_key) == current_key:
        return transcript_path

    suggestion = suggest_smart_rename_base_name(
        transcript_path,
        mode=mode,
        pattern=_smart_rename_pattern(),
    )
    if suggestion is None or not suggestion.full:
        st.session_state[processed_key] = current_key
        st.warning(
            "Auto-rename skipped: could not derive a date/time from the imported "
            "filename."
        )
        return transcript_path
    if suggestion.full == transcript_path.stem:
        st.session_state[processed_key] = current_key
        return transcript_path

    result = RenameService.rename_transcript_and_audio(
        transcript_path, suggestion.full
    )
    if result.ok and result.new_transcript_path:
        st.success(
            f"Auto-renamed to `{result.new_base_name}` "
            f"(pattern `{suggestion.pattern_used}`)."
        )
        new_path = Path(result.new_transcript_path)
        st.session_state[_KEY_LAST_IMPORTED_TRANSCRIPT_PATH] = str(new_path)
        st.session_state[processed_key] = str(new_path)
        _clear_import_caches()
        return new_path
    st.session_state[processed_key] = current_key
    st.warning(
        f"Auto-rename to `{suggestion.full}` failed: {result.message}. "
        "You can rename manually below."
    )
    return transcript_path


def _render_import_rename_form(transcript_path: Path) -> None:
    mode = _smart_rename_mode()
    # suggest_rename_only / off: still offer a manual rename form without smart UX.
    enable_smart = mode in {"suggest_import", "auto_import"}
    render_transcript_rename_form(
        transcript_path,
        form_key="import_rename_form",
        title="Rename imported transcript + linked audio",
        caption=(
            "Optional. This keeps transcript and linked audio filenames aligned. "
            "Extensions are preserved automatically."
        ),
        submit_label="Rename files",
        as_subheader=True,
        date_prefix_prefill=enable_smart,
        enable_smart=enable_smart,
    )


def _invalidate_scan_if_path_changed(path_value: str) -> None:
    handle = ScanHandle.from_session_dict(st.session_state.get(_KEY_SCAN_HANDLE))
    if handle is None:
        return
    if not scan_handle_still_valid(handle, path_input=path_value):
        st.session_state.pop(_KEY_SCAN_HANDLE, None)


def _on_scan_folder() -> None:
    """Run scan in on_click so Import eligible sees the handle on the same rerun."""
    path_value = str(st.session_state.get(_KEY_FOLDER_PATH) or "")
    handle = scan_folder_for_import(path_value)
    if not handle.closed_ok:
        st.session_state.pop(_KEY_SCAN_HANDLE, None)
        st.session_state[_KEY_SCAN_BANNER] = (
            "error",
            handle.error or "Scan failed.",
        )
        return
    st.session_state[_KEY_SCAN_HANDLE] = handle.to_session_dict()
    st.session_state[_KEY_SCAN_BANNER] = (
        "success",
        f"Scan complete: {len(handle.candidates)} supported file(s) "
        f"({len(eligible_candidates(handle))} eligible).",
    )


def _render_folder_import_section() -> None:
    st.subheader("2. Import all from folder")
    st.caption(
        "Scan an absolute local folder for supported transcript files. "
        "Eligible statuses: **new**, **incomplete (repairable)**, and "
        "**needs registration**. Already-managed stems and conflicts are blocked. "
        "Docker must mount the host folder into the container. Source files are "
        "never deleted or modified."
    )

    try:
        from transcriptx.services.watcher import get_watcher_service

        watcher_status = get_watcher_service().status()
        if watcher_status.enabled:
            paths = ", ".join(watcher_status.watch_paths) or "(no paths)"
            imported = watcher_status.job_counts.get("imported", 0)
            queued = watcher_status.job_counts.get("queued_transcription", 0)
            running = "running" if watcher_status.running else "enabled but not running"
            st.info(
                f"Directory watcher {running}: {paths} — "
                f"{imported} imported, {queued} queued. Configure in Settings → Watcher."
            )
    except Exception:
        pass

    path_value = st.text_input(
        "Folder path (absolute)",
        key=_KEY_FOLDER_PATH,
        help=(
            "Example: /Users/you/Documents/whisper-out. "
            "Must be absolute. Relative paths are rejected."
        ),
    )
    _invalidate_scan_if_path_changed(path_value or "")

    existing_handle = ScanHandle.from_session_dict(
        st.session_state.get(_KEY_SCAN_HANDLE)
    )
    scan_label = (
        "Rescan"
        if existing_handle and existing_handle.closed_ok
        else "Scan folder"
    )

    col_scan, col_import = st.columns(2)
    with col_scan:
        st.button(
            scan_label,
            key="import_folder_scan_btn",
            on_click=_on_scan_folder,
        )
    with col_import:
        handle = ScanHandle.from_session_dict(st.session_state.get(_KEY_SCAN_HANDLE))
        can_import = bool(
            handle
            and handle.closed_ok
            and scan_handle_still_valid(handle, path_input=path_value or "")
            and eligible_candidates(handle)
        )
        import_clicked = st.button(
            "Import eligible",
            key="import_folder_import_btn",
            type="primary",
            disabled=not can_import,
        )

    banner = st.session_state.pop(_KEY_SCAN_BANNER, None)
    if isinstance(banner, tuple) and len(banner) == 2:
        kind, message = banner
        if kind == "error":
            st.error(message)
        else:
            st.success(message)

    handle = ScanHandle.from_session_dict(st.session_state.get(_KEY_SCAN_HANDLE))
    if handle and handle.closed_ok:
        eligible_count = 0
        blocked_count = 0
        label_counts: dict[str, int] = {}
        for cand in handle.candidates:
            label = status_label(cand.status)
            label_counts[label] = label_counts.get(label, 0) + 1
            if is_eligible_status(cand.status):
                eligible_count += 1
            else:
                blocked_count += 1
        st.write(
            f"Preview — Eligible: {eligible_count}, Blocked: {blocked_count}"
            + (
                " · "
                + ", ".join(f"{k}: {v}" for k, v in sorted(label_counts.items()))
                if label_counts
                else ""
            )
        )
        rows = [
            {
                "file": c.basename,
                "status": status_label(c.status),
                "eligible": "yes" if is_eligible_status(c.status) else "no",
                "audio": c.audio_hint or "none",
                "detail": c.secondary_detail or status_help(c.status),
            }
            for c in handle.candidates
        ]
        st.dataframe(rows, hide_index=True, width="stretch")

        if handle.candidates and not eligible_candidates(handle):
            st.info("No eligible files to import from this scan.")

    if import_clicked:
        handle = ScanHandle.from_session_dict(st.session_state.get(_KEY_SCAN_HANDLE))
        if not handle or not scan_handle_still_valid(
            handle, path_input=path_value or ""
        ):
            st.error("Scan preview is no longer valid. Scan the folder again.")
            st.session_state.pop(_KEY_SCAN_HANDLE, None)
            return

        eligible = eligible_candidates(handle)
        progress = st.progress(0.0, text="Importing…")
        outcomes = []
        for idx, cand in enumerate(eligible):
            progress.progress(
                idx / max(len(eligible), 1),
                text=f"Importing {cand.basename} ({idx + 1}/{len(eligible)})",
            )
            batch = import_folder_candidates(
                handle, path_input=path_value or "", only=[cand]
            )
            outcomes.extend(batch)
        progress.progress(1.0, text="Done")

        progressed = False
        last_path: Path | None = None
        success_kinds = {
            AdmitOutcomeKind.IMPORTED_AND_REGISTERED,
            AdmitOutcomeKind.PARTIAL_STATE_REPAIRED,
            AdmitOutcomeKind.REGISTRATION_RECOVERED,
        }
        for outcome in outcomes:
            if outcome.artifact_committed or outcome.registration_progressed:
                progressed = True
            if outcome.transcript_path is not None and outcome.kind in success_kinds:
                last_path = outcome.transcript_path
            if outcome.kind in success_kinds:
                st.success(outcome.user_safe_detail)
            elif outcome.kind in {
                AdmitOutcomeKind.ALREADY_MANAGED,
                AdmitOutcomeKind.CONCURRENT_SKIP,
            }:
                st.info(outcome.user_safe_detail)
            elif outcome.kind is AdmitOutcomeKind.STALE_CANDIDATE:
                st.warning(outcome.user_safe_detail)
            else:
                st.error(outcome.user_safe_detail)

        missing_audio_stems = [
            cand.display_stem
            for cand in eligible
            if (cand.audio_hint or "none") == "none"
        ]
        if last_path is not None and missing_audio_stems:
            stems = ", ".join(sorted(set(missing_audio_stems)))
            st.info(
                "No same-stem audio under recordings for: "
                f"**{stems}**. Upload via section 3 or place "
                "`{stem}.mp3` (or wav/m4a/…) in the recordings folder for playback linking."
            )

        if progressed:
            _clear_import_caches()
            # Auto-rescan so preview shows already_managed / updated statuses.
            if path_value:
                _on_scan_folder()
                refreshed = ScanHandle.from_session_dict(
                    st.session_state.get(_KEY_SCAN_HANDLE)
                )
                if refreshed and refreshed.closed_ok:
                    st.caption(
                        "Folder rescanned after import — open Rescan or re-render "
                        "to refresh the preview table if needed."
                    )
        if last_path is not None:
            st.session_state[_KEY_LAST_IMPORTED_TRANSCRIPT_PATH] = str(last_path)


def render_upload_transcript_page() -> None:
    """Render the Import Transcript page."""
    st.markdown(
        '<div class="main-header">Import Transcript</div>',
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
            type=list(SUPPORTED_IMPORT_UPLOAD_TYPES),
            accept_multiple_files=True,
            help=(
                "JSON (TranscriptX, Whisper, Sembly), SRT, VTT, HTML "
                "(e.g. Sembly export), or other supported formats."
            ),
            key="upload_transcript_file",
        )
        import_submitted = st.form_submit_button(
            "Import Transcript",
            type="primary",
            width="content",
        )

    if import_submitted:
        if not uploaded_transcripts:
            st.error("Please choose a transcript file to import.")
        else:
            successes: list[str] = []
            failures: list[tuple[str, str]] = []
            for uploaded_transcript in uploaded_transcripts:
                try:
                    kind = _import_uploaded_transcript(uploaded_transcript)
                except Exception as e:
                    logger.exception("Import failed")
                    failures.append((uploaded_transcript.name, str(e)))
                else:
                    successes.append(f"{uploaded_transcript.name} ({kind.value})")

            if successes:
                st.success(f"Processed {len(successes)} transcript(s).")
                for line in successes:
                    st.caption(line)
            if failures:
                st.error(f"{len(failures)} import(s) failed.")
                for filename, message in failures:
                    st.caption(f"`{filename}`: {message}")

    imported_path = st.session_state.get(_KEY_LAST_IMPORTED_TRANSCRIPT_PATH)
    if imported_path:
        current = _maybe_auto_rename_imported(Path(imported_path))
        _render_post_import_actions(current)
        _render_import_rename_form(current)

    _render_folder_import_section()

    st.subheader("3. Optional recording upload")
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
            help=(
                "This stores audio for speaker identification and voice/audio "
                "feature modules. It does not generate transcript text."
            ),
            key="upload_optional_recording_file",
        )
        recording_submitted = st.form_submit_button("Upload Recording")

    if recording_submitted:
        if not uploaded_recording:
            st.info("No recording selected. Transcript import works without audio.")
        else:
            try:
                saved_recording = RecordingsService.save_uploaded_file(
                    uploaded_recording
                )
            except Exception as e:
                logger.exception("Recording upload failed")
                st.error(f"Recording upload failed: {e}")
            else:
                _clear_import_caches()
                st.success(f"Saved recording to `{saved_recording}`.")
                st.caption(
                    "This recording is available for speaker identification and "
                    "audio-derived features."
                )
