"""
Transcribe Audio — integrated transcription page (macOS whispermlx v1).
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import streamlit as st

from transcriptx.app.controllers.merge_controller import MergeController
from transcriptx.app.controllers.transcription_controller import (
    TranscriptionController,
)
from transcriptx.app.models.requests import (
    MergeRequest,
    TranscriptionConversionOptions,
    TranscriptionOptions,
    TranscriptionRequest,
)
from transcriptx.app.models.results import MergeResult, TranscriptionBatchResult
from transcriptx.app.progress import make_initial_snapshot
from transcriptx.core.audio.types import SUPPORTED_AUDIO_EXTENSIONS
from transcriptx.core.audio.serial_groups import (
    SerialGroup,
    detect_serial_audio_groups,
    merged_output_filename,
)
from transcriptx.core.utils.paths import PATHS, RECORDINGS_DIR, RECORDINGS_IMPORTS_DIR
from transcriptx.services.transcription.env import (
    default_conversion_options,
    default_request_flags,
    default_transcription_options,
)
from transcriptx.services.transcription.registry import get_transcription_providers
from transcriptx.web.components.progress_panel import (
    MERGE_SNAPSHOT_KEY,
    TRANSCRIPTION_SNAPSHOT_KEY,
    StreamlitProgressCallback,
    render_progress_panel,
)
from transcriptx.web.components.serial_group_prompt import render_serial_group_prompt
from transcriptx.web.navigation import (
    consume_transcription_nav_paths,
    navigate_to_audio_merge_with_paths,
)
from transcriptx.web.services.recordings_service import RecordingsService

_KEY_RUN_IN_PROGRESS = "transcription_run_in_progress"
_KEY_RESULT = "transcription_run_result"
_KEY_FOLDER_PREVIEW = "transcription_folder_preview_paths"
_KEY_LARGE_BATCH_OK = "transcription_large_batch_ok"
_KEY_SERIAL_SEPARATE_OK = "transcription_serial_separate_ok"
_KEY_MERGE_BUTTON = "transcription_merge_and_transcribe"
_KEY_REVIEW_MERGE_BUTTON = "transcription_review_in_audio_merge"
_MERGE_STAGE_COUNT = 4

_FOLDER_PREVIEW_CAP = 20
_LARGE_BATCH_THRESHOLD = 50


def _scan_folder(
    folder: Path, *, recursive: bool, extensions: frozenset[str]
) -> list[Path]:
    if not folder.is_dir():
        return []
    iterator = folder.rglob("*") if recursive else folder.glob("*")
    return sorted(
        p.resolve() for p in iterator if p.is_file() and p.suffix.lower() in extensions
    )


def _list_pickable_recordings() -> list[Path]:
    recordings = RecordingsService.list_recordings(RECORDINGS_DIR)
    if RECORDINGS_IMPORTS_DIR != RECORDINGS_DIR / "imports":
        imports_files = RecordingsService.list_recordings(RECORDINGS_IMPORTS_DIR)
        seen = {p.resolve() for p in recordings}
        for p in imports_files:
            if p.resolve() not in seen:
                recordings.append(p)
        recordings.sort(key=lambda p: p.name)
    return recordings


def _provider_labels() -> dict[str, str]:
    return {p.provider_id: p.info().label for p in get_transcription_providers()}


def _render_readiness(options: TranscriptionOptions) -> bool:
    providers = {p.provider_id: p for p in get_transcription_providers()}
    provider = providers.get(options.provider_id)
    if provider is None:
        st.error(f"Unknown provider: {options.provider_id}")
        return False
    availability = provider.is_available(options)
    for check in availability.checks:
        icon = "✅" if check.passed else "❌"
        detail = f" — {check.message}" if check.message and not check.passed else ""
        st.caption(f"{icon} {check.label}{detail}")
    if not availability.available and availability.reason:
        st.warning(availability.reason)
    return availability.available


def _render_provider_help(provider_id: str) -> None:
    if provider_id == "whispermlx":
        st.markdown(
            "Install **whispermlx** on macOS and ensure **ffmpeg** is on PATH. "
            "Set `WHISPERMLX` in `whisperx.env` if the binary is not found via "
            "`which whispermlx`. "
            "Set `HF_TOKEN` only when diarization is enabled."
        )
    elif provider_id == "whisperx_docker":
        st.markdown(
            "WhisperX Docker GUI orchestration is coming soon. "
            "See the external recipe at "
            "`docs/recipes/whisperx/README.md` for manual use."
        )


def _render_results(result: TranscriptionBatchResult) -> None:
    st.subheader("Results")
    st.markdown(
        f"**{result.succeeded_count}/{len(result.file_results)}** succeeded "
        f"· job `{result.job_id}` · output `{result.output_dir}`"
    )
    for file_result in result.file_results:
        with st.expander(
            f"{'✅' if file_result.success else '❌'} {file_result.input_path.name}",
            expanded=not file_result.success,
        ):
            st.text(f"Input: {file_result.input_path}")
            st.text(f"Provider: {file_result.provider_id}")
            if file_result.raw_json_path:
                st.text(f"Raw JSON: {file_result.raw_json_path}")
            if file_result.imported_json_path:
                st.text(f"Imported: {file_result.imported_json_path}")
            if file_result.staged_mp3_path:
                st.text(f"Staged MP3: {file_result.staged_mp3_path}")
            if file_result.import_success is not None:
                st.text(
                    f"Import: {'succeeded' if file_result.import_success else 'failed'}"
                )
            if file_result.errors:
                st.error("\n".join(file_result.errors))
            if file_result.stderr_tail:
                st.code("\n".join(file_result.stderr_tail))


def _collect_input_paths(
    tab: str,
    upload_paths: List[Path],
    pick_paths: List[Path],
    folder_paths: List[Path],
) -> list[Path]:
    if tab == "Upload":
        return upload_paths
    if tab == "Pick existing":
        return pick_paths
    return folder_paths


def replace_grouped_paths_with_merged(
    input_paths: list[Path],
    groups: list[SerialGroup],
    merged_outputs: dict[str, Path],
) -> list[Path]:
    """Replace grouped input paths with merged MP3 paths; preserve order."""
    path_to_base: dict[Path, str] = {}
    for group in groups:
        for path in group.ordered_paths:
            try:
                path_to_base[path.resolve()] = group.base_key
            except OSError:
                path_to_base[path] = group.base_key

    result: list[Path] = []
    emitted_merged: set[str] = set()
    for path in input_paths:
        try:
            lookup = path.resolve()
        except OSError:
            lookup = path
        base_key = path_to_base.get(lookup)
        if base_key is None:
            result.append(path)
            continue
        if base_key in emitted_merged:
            continue
        result.append(merged_outputs[base_key])
        emitted_merged.add(base_key)
    return result


def _merge_serial_groups(
    groups: list[SerialGroup],
    *,
    progress_snapshot_key: str,
) -> tuple[dict[str, Path], MergeResult | None]:
    """Merge each serial group; return merged paths keyed by base_key."""
    merged_outputs: dict[str, Path] = {}
    merge_ctrl = MergeController()
    st.session_state[progress_snapshot_key] = make_initial_snapshot(
        total=_MERGE_STAGE_COUNT
    )
    progress = StreamlitProgressCallback(progress_snapshot_key)

    for group in groups:
        request = MergeRequest(
            file_paths=list(group.ordered_paths),
            output_dir=Path(RECORDINGS_DIR),
            output_filename=merged_output_filename(group.base_key),
            backup_wavs=True,
            overwrite=False,
        )
        result = merge_ctrl.run_merge(request, progress=progress)
        if not result.success or result.output_path is None:
            return {}, result
        merged_outputs[group.base_key] = result.output_path
    return merged_outputs, None


def _run_transcription_job(
    input_paths: list[Path],
    *,
    options: TranscriptionOptions,
    conversion_options: TranscriptionConversionOptions,
    out_dir: Path | None,
    import_into_library: bool,
    overwrite_import: bool,
    keep_intermediates: bool,
) -> None:
    request = TranscriptionRequest(
        input_paths=input_paths,
        transcription_options=options,
        conversion_options=conversion_options,
        output_dir=out_dir,
        import_into_library=import_into_library,
        overwrite_import=overwrite_import,
        keep_intermediates=keep_intermediates,
    )

    st.session_state[TRANSCRIPTION_SNAPSHOT_KEY] = make_initial_snapshot(
        total=len(input_paths)
    )
    st.session_state[_KEY_RUN_IN_PROGRESS] = True
    progress = StreamlitProgressCallback(TRANSCRIPTION_SNAPSHOT_KEY)
    ctrl = TranscriptionController()

    with st.status("Transcribing…", expanded=True) as status_widget:
        try:
            result = ctrl.run_transcription(request, progress=progress)
        except Exception as exc:
            result = TranscriptionBatchResult(
                job_id="",
                success=False,
                file_results=[],
                succeeded_count=0,
                failed_count=len(input_paths),
                output_dir=PATHS.data_dir / "transcription" / "output",
                errors=[str(exc)],
            )
        finally:
            st.session_state[_KEY_RUN_IN_PROGRESS] = False
        if result.success:
            status_widget.update(label="✓ Complete", state="complete")
        else:
            status_widget.update(label="✗ Finished with errors", state="error")

    st.session_state[_KEY_RESULT] = result
    st.rerun()


def render_transcribe_audio_page() -> None:
    """Render integrated transcription UI."""
    st.markdown(
        '<div class="main-header">🎙️ Transcribe Audio</div>',
        unsafe_allow_html=True,
    )
    st.info(
        "Integrated transcription is fully supported on **macOS with whispermlx**. "
        "Other providers appear below for future support."
    )

    env_defaults = default_transcription_options()
    conv_defaults = default_conversion_options()
    request_defaults = default_request_flags()
    providers = get_transcription_providers()
    provider_ids = [p.provider_id for p in providers]
    labels = _provider_labels()

    default_provider_idx = (
        provider_ids.index(env_defaults.provider_id)
        if env_defaults.provider_id in provider_ids
        else 0
    )

    provider_id = st.selectbox(
        "Transcription provider",
        options=provider_ids,
        index=default_provider_idx,
        format_func=lambda pid: labels.get(pid, pid),
        key="transcription_provider",
    )

    model = st.text_input("Model", value=env_defaults.model, key="transcription_model")
    language = st.text_input(
        "Language", value=env_defaults.language, key="transcription_language"
    )
    diarize = st.checkbox(
        "Enable diarization", value=env_defaults.diarize, key="transcription_diarize"
    )
    timeout_seconds = st.number_input(
        "Timeout per file (seconds, 0 = no limit)",
        min_value=0,
        value=env_defaults.timeout_seconds,
        step=60,
        key="transcription_timeout",
    )

    options = TranscriptionOptions(
        provider_id=provider_id,
        model=model.strip(),
        language=language.strip(),
        diarize=diarize,
        timeout_seconds=int(timeout_seconds),
    )

    st.markdown("**Readiness**")
    provider_ready = _render_readiness(options)

    with st.expander("Provider setup help", expanded=False):
        _render_provider_help(provider_id)

    upload_paths: List[Path] = []
    pick_paths: List[Path] = []
    folder_paths: List[Path] = []

    tab_upload, tab_pick, tab_folder = st.tabs(
        ["Upload", "Pick existing", "Folder path"]
    )

    with tab_upload:
        uploaded_list = st.file_uploader(
            "Upload audio file(s)",
            type=[ext.lstrip(".") for ext in sorted(SUPPORTED_AUDIO_EXTENSIONS)],
            accept_multiple_files=True,
            max_upload_size=500,
            key="transcription_upload",
        )
        if uploaded_list:
            for uploaded in uploaded_list:
                saved = RecordingsService.save_uploaded_file(uploaded)
                upload_paths.append(saved)
            st.caption(f"{len(upload_paths)} file(s) saved to imports.")

    with tab_pick:
        recordings = _list_pickable_recordings()
        paths_str = [str(p) for p in recordings]
        nav_paths = consume_transcription_nav_paths(st.session_state)
        if nav_paths:
            valid_nav = [p for p in nav_paths if p in paths_str]
            if valid_nav:
                st.session_state["transcription_pick"] = valid_nav
        selected = st.multiselect(
            "Select recording(s)",
            options=paths_str,
            format_func=lambda p: Path(p).name,
            key="transcription_pick",
        )
        pick_paths = [Path(p) for p in selected]
        if pick_paths:
            for p in pick_paths[:5]:
                meta = RecordingsService.get_audio_metadata(p)
                st.caption(
                    f"{p.name}: {RecordingsService.format_duration(meta['duration_sec'])}"
                    f", {meta['file_size_mb']} MB"
                )

    with tab_folder:
        st.caption("Path is read from the machine running Streamlit, not your browser.")
        folder_input = st.text_input(
            "Absolute folder path",
            value="",
            key="transcription_folder_path",
        )
        recursive = st.checkbox(
            "Recursive scan", value=True, key="transcription_recursive"
        )
        if st.button("Preview files", key="transcription_preview_folder"):
            folder = Path(folder_input).expanduser()
            if not folder.is_dir():
                st.error("Folder does not exist or is not a directory.")
                st.session_state[_KEY_FOLDER_PREVIEW] = []
            elif not folder.exists():
                st.error("Folder not found.")
                st.session_state[_KEY_FOLDER_PREVIEW] = []
            else:
                try:
                    scanned = _scan_folder(
                        folder.resolve(),
                        recursive=recursive,
                        extensions=SUPPORTED_AUDIO_EXTENSIONS,
                    )
                except OSError as exc:
                    st.error(f"Cannot read folder: {exc}")
                    scanned = []
                st.session_state[_KEY_FOLDER_PREVIEW] = [str(p) for p in scanned]

        preview_strs: list[str] = st.session_state.get(_KEY_FOLDER_PREVIEW, [])
        folder_paths = [Path(p) for p in preview_strs]
        if preview_strs:
            st.caption(f"{len(preview_strs)} file(s) found.")
            for p in preview_strs[:_FOLDER_PREVIEW_CAP]:
                st.text(p)
            if len(preview_strs) > _FOLDER_PREVIEW_CAP:
                st.caption(
                    f"… and {len(preview_strs) - _FOLDER_PREVIEW_CAP} more not shown."
                )

    active_tab = st.radio(
        "Input source for run",
        options=["Upload", "Pick existing", "Folder path"],
        horizontal=True,
        key="transcription_active_tab",
    )
    input_paths = _collect_input_paths(
        active_tab, upload_paths, pick_paths, folder_paths
    )
    serial_groups = detect_serial_audio_groups(input_paths)

    st.markdown("**Transcription settings**")
    import_into_library = st.checkbox(
        "Import into library when done",
        value=request_defaults["import_into_library"],
        key="transcription_import",
    )
    overwrite_import = st.checkbox(
        "Overwrite existing transcript if names collide",
        value=request_defaults["overwrite_import"],
        key="transcription_overwrite_import",
    )
    output_dir_override = st.text_input(
        "Output directory override (optional)",
        value="",
        key="transcription_output_dir",
    )
    keep_intermediates = st.checkbox(
        "Keep intermediate staged MP3 files",
        value=request_defaults["keep_intermediates"],
        key="transcription_keep_intermediates",
    )

    with st.expander("Conversion settings", expanded=False):
        bitrate = st.text_input(
            "MP3 bitrate", value=conv_defaults.bitrate, key="transcription_bitrate"
        )
        channels = st.number_input(
            "Channels",
            min_value=1,
            max_value=2,
            value=conv_defaults.channels,
            key="transcription_channels",
        )
        sample_rate = st.number_input(
            "Sample rate (0 = keep source)",
            min_value=0,
            value=conv_defaults.sample_rate,
            step=1000,
            key="transcription_sample_rate",
        )
        force_reencode = st.checkbox(
            "Force re-encode MP3",
            value=conv_defaults.force_reencode,
            key="transcription_force_reencode",
        )

    conversion_options = TranscriptionConversionOptions(
        codec=conv_defaults.codec,
        bitrate=bitrate.strip(),
        channels=int(channels),
        sample_rate=int(sample_rate),
        force_reencode=force_reencode,
    )

    serial_prompt_state = None
    if serial_groups:
        st.markdown("**Split recording detection**")
        serial_prompt_state = render_serial_group_prompt(
            serial_groups,
            separate_ok_key=_KEY_SERIAL_SEPARATE_OK,
            merge_button_key=_KEY_MERGE_BUTTON,
            review_button_key=_KEY_REVIEW_MERGE_BUTTON,
            duration_lookup=lambda p: RecordingsService.get_audio_metadata(p)[
                "duration_sec"
            ],
        )
        if serial_prompt_state.review_in_merge_clicked:
            navigate_to_audio_merge_with_paths(
                st.session_state, list(serial_groups[0].ordered_paths)
            )
            if len(serial_groups) > 1:
                st.session_state["transcription_serial_review_note"] = (
                    f"Opened first of {len(serial_groups)} detected groups in Audio Merge."
                )
            st.rerun()

    large_batch = len(input_paths) > _LARGE_BATCH_THRESHOLD
    large_batch_ok = True
    if large_batch:
        st.warning(
            f"This batch has {len(input_paths)} files (>{_LARGE_BATCH_THRESHOLD}). "
            "Transcription may take a long time."
        )
        large_batch_ok = st.checkbox(
            "I understand this may take a long time",
            value=st.session_state.get(_KEY_LARGE_BATCH_OK, False),
            key=_KEY_LARGE_BATCH_OK,
        )

    serial_separate_ok = True
    if serial_groups:
        serial_separate_ok = bool(
            serial_prompt_state.transcribe_separately_ok
            if serial_prompt_state is not None
            else st.session_state.get(_KEY_SERIAL_SEPARATE_OK, False)
        )

    run_disabled = (
        not input_paths
        or not provider_ready
        or (active_tab == "Folder path" and not folder_paths)
        or (large_batch and not large_batch_ok)
        or (serial_groups and not serial_separate_ok)
    )
    disable_reason: Optional[str] = None
    if not input_paths:
        disable_reason = "Select at least one audio file."
    elif not provider_ready:
        disable_reason = "Selected provider is not ready."
    elif active_tab == "Folder path" and not folder_paths:
        disable_reason = "Preview folder files before running."
    elif large_batch and not large_batch_ok:
        disable_reason = "Confirm the large-batch warning."
    elif serial_groups and not serial_separate_ok:
        disable_reason = (
            "Merge detected groups first, or acknowledge separate transcription."
        )

    review_note = st.session_state.pop("transcription_serial_review_note", None)
    if review_note:
        st.info(review_note)

    if st.session_state.get(_KEY_RUN_IN_PROGRESS, False):
        snapshot = st.session_state.get(TRANSCRIPTION_SNAPSHOT_KEY)
        if snapshot is not None:
            render_progress_panel(
                snapshot,
                unit_label="files",
                current_label="Current file",
            )
        else:
            st.info("Transcribing…")
        return

    last_result: Optional[TranscriptionBatchResult] = st.session_state.get(_KEY_RESULT)
    if last_result is not None:
        _render_results(last_result)

    if disable_reason:
        st.caption(disable_reason)

    merge_and_transcribe_clicked = bool(
        serial_prompt_state is not None
        and serial_prompt_state.merge_and_transcribe_clicked
    )

    if merge_and_transcribe_clicked and serial_groups:
        out_dir: Path | None = None
        if output_dir_override.strip():
            out_dir = Path(output_dir_override).expanduser()

        with st.status("Merging detected groups…", expanded=True) as merge_status:
            merged_outputs, merge_failure = _merge_serial_groups(
                serial_groups,
                progress_snapshot_key=MERGE_SNAPSHOT_KEY,
            )
            if merge_failure is not None:
                merge_status.update(label="✗ Merge failed", state="error")
                st.error("Merge failed. Transcription was not started.")
                for err in merge_failure.errors:
                    st.error(err)
                if st.button(
                    "Review in Audio Merge", key="transcription_merge_fail_review"
                ):
                    navigate_to_audio_merge_with_paths(
                        st.session_state, list(serial_groups[0].ordered_paths)
                    )
                    st.rerun()
            else:
                merge_status.update(label="✓ Merge complete", state="complete")
                transcription_paths = replace_grouped_paths_with_merged(
                    input_paths, serial_groups, merged_outputs
                )
                _run_transcription_job(
                    transcription_paths,
                    options=options,
                    conversion_options=conversion_options,
                    out_dir=out_dir,
                    import_into_library=import_into_library,
                    overwrite_import=overwrite_import,
                    keep_intermediates=keep_intermediates,
                )
        return

    if st.button(
        f"▶ Transcribe {len(input_paths)} file(s)" if input_paths else "▶ Transcribe",
        type="primary",
        disabled=run_disabled,
        key="transcription_run",
    ):
        out_dir = None
        if output_dir_override.strip():
            out_dir = Path(output_dir_override).expanduser()

        _run_transcription_job(
            input_paths,
            options=options,
            conversion_options=conversion_options,
            out_dir=out_dir,
            import_into_library=import_into_library,
            overwrite_import=overwrite_import,
            keep_intermediates=keep_intermediates,
        )
