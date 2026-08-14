"""
Audio merge workflow — no Streamlit or presentation-layer concerns.

Progress uses four stages (always, for a consistent UI mental model):
    validating → backing_up → merging → completed

When backup is disabled, the backing_up stage is skipped via on_stage_progress
and the workflow advances immediately to merging. Original deletion, when
requested, runs in the completed stage and only after a non-empty output exists.
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from transcriptx.app.models.requests import MergeRequest
from transcriptx.app.models.results import MergeResult
from transcriptx.app.progress import NullProgress, ProgressCallback
from transcriptx.core.audio.backup import backup_audio_files_to_storage
from transcriptx.core.audio.conversion import merge_audio_files
from transcriptx.core.audio.linked_transcripts import (
    delete_linked_transcripts_for_audio,
)
from transcriptx.core.audio.tools import check_ffmpeg_available
from transcriptx.core.utils.rename.date_prefix import extract_date_prefix
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import RECORDINGS_DIR

logger = get_logger()

_SUPPORTED_EXTENSIONS = frozenset(
    {".wav", ".mp3", ".ogg", ".m4a", ".flac", ".aac", ".wma"}
)

# Total stage count — always 4 so the snapshot total is constant
_TOTAL_STAGES = 4


def _delete_merge_originals(
    sources: list[Path],
    output_path: Path,
) -> tuple[int, int, list[str]]:
    """Delete source audio and linked part transcripts. Never touches the output."""
    audio_deleted = 0
    transcripts_deleted = 0
    warnings: list[str] = []
    try:
        output_resolved = output_path.resolve()
    except OSError:
        output_resolved = output_path

    for src in sources:
        try:
            resolved = src.resolve()
        except OSError:
            resolved = src
        if resolved == output_resolved:
            continue
        tx_count, tx_warnings = delete_linked_transcripts_for_audio(src)
        transcripts_deleted += tx_count
        warnings.extend(tx_warnings)
        if not src.is_file():
            continue
        try:
            src.unlink()
            audio_deleted += 1
            logger.info("Deleted merge original: %s", src)
        except OSError as exc:
            warnings.append(f"Could not delete original {src.name}: {exc}")
    return audio_deleted, transcripts_deleted, warnings


def run_merge(
    request: MergeRequest,
    progress: ProgressCallback | None = None,
) -> MergeResult:
    """
    Merge a list of audio files into a single MP3.

    Progress stages (total=4, always):
        1. validating
        2. backing_up   (skipped when request.backup_wavs is False)
        3. merging
        4. completed    (deletes originals here when request.delete_originals)

    Returns a MergeResult on both success and handled failure so callers
    never need to catch expected errors.  Unexpected exceptions propagate
    and should be caught by the controller.
    """
    if progress is None:
        progress = NullProgress()

    warnings: list[str] = []

    # ------------------------------------------------------------------
    # Stage 1: Validate
    # ------------------------------------------------------------------
    progress.on_stage_start("validating")

    ffmpeg_ok, ffmpeg_err = check_ffmpeg_available()
    if not ffmpeg_ok:
        progress.on_stage_complete("validating")
        return MergeResult(
            success=False,
            errors=[f"ffmpeg is not available: {ffmpeg_err}"],
        )

    file_paths = request.file_paths
    if len(file_paths) < 2:
        progress.on_stage_complete("validating")
        return MergeResult(
            success=False,
            errors=["At least 2 audio files are required for merging."],
        )

    seen: set[Path] = set()
    duplicates: list[str] = []
    for p in file_paths:
        if p in seen:
            duplicates.append(str(p))
        else:
            seen.add(p)
    if duplicates:
        progress.on_stage_complete("validating")
        return MergeResult(
            success=False,
            errors=[f"Duplicate files in list: {', '.join(duplicates)}"],
        )

    missing = [str(p) for p in file_paths if not p.exists()]
    if missing:
        progress.on_stage_complete("validating")
        return MergeResult(
            success=False,
            errors=[f"File(s) not found: {', '.join(missing)}"],
        )

    bad_ext = [
        str(p) for p in file_paths if p.suffix.lower() not in _SUPPORTED_EXTENSIONS
    ]
    if bad_ext:
        progress.on_stage_complete("validating")
        return MergeResult(
            success=False,
            errors=[
                f"Unsupported file format(s): {', '.join(bad_ext)}. "
                f"Supported: {', '.join(sorted(_SUPPORTED_EXTENSIONS))}"
            ],
        )

    output_dir = (
        Path(request.output_dir) if request.output_dir else Path(RECORDINGS_DIR)
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    if request.output_filename:
        output_filename = request.output_filename
        if not output_filename.endswith(".mp3"):
            output_filename += ".mp3"
    else:
        date_prefix = extract_date_prefix(file_paths[0])
        if date_prefix:
            output_filename = f"{date_prefix}merged.mp3"
        else:
            output_filename = f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"

    output_path = output_dir / output_filename

    # Output must not be one of the inputs
    resolved_inputs = {p.resolve() for p in file_paths}
    if output_path.resolve() in resolved_inputs:
        progress.on_stage_complete("validating")
        return MergeResult(
            success=False,
            errors=[
                f"Output path '{output_path}' is the same as one of the input files."
            ],
        )

    if output_path.exists() and not request.overwrite:
        progress.on_stage_complete("validating")
        return MergeResult(
            success=False,
            errors=[
                f"Output file already exists: {output_path}. "
                "Enable 'Overwrite if exists' to replace it."
            ],
        )

    progress.on_log(f"Validated {len(file_paths)} input files → {output_filename}")
    progress.on_stage_complete("validating")

    # ------------------------------------------------------------------
    # Stage 2: Backup (or skip)
    # ------------------------------------------------------------------
    progress.on_stage_start("backing_up")

    merge_files = list(file_paths)

    if request.backup_wavs:
        progress.on_stage_progress("Backing up originals to storage…")
        try:
            base_name = Path(output_filename).stem
            backed_up = backup_audio_files_to_storage(merge_files, base_name=base_name)
            if backed_up:
                progress.on_log(f"Backed up {len(backed_up)} file(s) to storage")
                merge_files = backed_up
            else:
                msg = "Backup produced no output files; continuing with originals."
                logger.warning(msg)
                warnings.append(msg)
        except Exception as exc:
            msg = f"Backup of originals failed: {exc}. Merge will continue with originals."
            logger.warning(msg)
            warnings.append(msg)
    else:
        progress.on_stage_progress("Backup skipped (disabled).")
        progress.on_log("Backup skipped (backup_wavs=False)")

    progress.on_stage_complete("backing_up")

    # ------------------------------------------------------------------
    # Stage 3: Merge
    # ------------------------------------------------------------------
    progress.on_stage_start("merging")
    progress.on_log(f"Merging {len(merge_files)} files → {output_filename}")
    if request.apply_preprocessing:
        progress.on_log("Preprocessing enabled for this merge pass")

    t0 = time.time()

    total_files = len(merge_files)

    def _progress_cb(current: int, total: int, message: str) -> None:
        pct = (current / total * 100.0) if total else None
        progress.on_stage_progress(message, pct)  # type: ignore[union-attr]
        progress.on_log(message)  # type: ignore[union-attr]

    try:
        result_path = merge_audio_files(
            merge_files,
            output_path,
            progress_callback=_progress_cb,
            apply_preprocessing_steps=request.apply_preprocessing,
        )
    except Exception as exc:
        progress.on_stage_complete("merging")
        return MergeResult(
            success=False,
            errors=[f"Merge failed: {exc}"],
            warnings=warnings,
        )

    elapsed = time.time() - t0
    progress.on_log(
        f"Merged {total_files} files in {elapsed:.1f}s → {result_path.name}"
    )
    progress.on_stage_complete("merging")

    # ------------------------------------------------------------------
    # Stage 4: Completed (optional original deletion)
    # ------------------------------------------------------------------
    progress.on_stage_start("completed")
    files_deleted = 0
    transcripts_deleted = 0
    if request.delete_originals:
        output_ok = (
            result_path.exists()
            and result_path.is_file()
            and result_path.stat().st_size > 0
        )
        if not output_ok:
            warnings.append(
                "Skipped deleting originals because the merge output is missing or empty."
            )
            progress.on_log("Original deletion skipped (output missing or empty)")
        else:
            progress.on_stage_progress("Deleting original source files…")
            files_deleted, transcripts_deleted, delete_warnings = (
                _delete_merge_originals(file_paths, result_path)
            )
            warnings.extend(delete_warnings)
            progress.on_log(
                f"Deleted {files_deleted} original file(s) and "
                f"{transcripts_deleted} linked transcript(s)"
            )
    progress.on_stage_complete("completed")

    return MergeResult(
        success=True,
        output_path=result_path,
        files_merged=total_files,
        files_deleted=files_deleted,
        transcripts_deleted=transcripts_deleted,
        warnings=warnings,
    )
