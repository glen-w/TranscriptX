"""
File rename utilities for TranscriptX.

This module provides functionality to rename transcript files and their
associated output folders after speaker mapping is completed. The rename
operation updates all related files and references.

Rollback policy: ``RenameTransaction.rollback()`` is only for failures **during**
``execute()``. After ``execute()`` returns success (non-dry-run), the transaction
is committed; a later finalize failure must **not** call ``rollback()`` — finalize
is a separate boundary and may have partially moved output artifacts.
"""

import copy
import json
import shutil
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from transcriptx.core.utils.logger import get_logger, log_error
from transcriptx.core.utils.paths import (
    OUTPUTS_DIR,
    PROCESSING_STATE_FILE,
    RECORDINGS_DIR,
)
from transcriptx.core.utils._path_cache import invalidate_path_cache
from transcriptx.core.utils._path_core import (
    get_base_name,
    get_canonical_base_name,
    get_transcript_dir,
    strip_duplicate_filename_suffix,
)
from transcriptx.core.utils._path_resolution import resolve_file_path
from transcriptx.core.utils.rename_transaction import RenameTransaction
from transcriptx.io.import_metadata_sidecar import (
    append_rename_history,
    sidecar_path_for_transcript as import_meta_sidecar_path_for_transcript,
    validate_managed_transcript,
)
from transcriptx.io.speaker_map_resolver import sidecar_path_for

logger = get_logger()

ROLLBACK_POLICY = (
    "Use RenameTransaction.rollback() only for failures during execute(); "
    "never rollback to fix post-commit finalize failures."
)


@dataclass(frozen=True)
class RenameTranscriptOutcome:
    """Structured result for rename pipeline (transaction vs finalize boundaries).

    ``transaction_succeeded``: ``RenameTransaction.execute()`` returned True (or dry-run
    path that skips real I/O but is treated as success).

    ``transaction_committed``: non-dry-run execute succeeded; filesystem + processing
    state reflect transaction ops. **Do not** call ``RenameTransaction.rollback()`` for
    a later finalize failure — finalize is a separate boundary and may have partially
    mutated the output tree.
    """

    transaction_attempted: bool
    transaction_succeeded: bool
    transaction_committed: bool
    finalize_attempted: bool
    finalize_succeeded: bool
    warnings: list[str] = field(default_factory=list)
    last_error: Optional[str] = None

    @property
    def ok(self) -> bool:
        """True when both transaction and finalize stages succeeded (legacy bool)."""
        return self.transaction_succeeded and self.finalize_succeeded

    @property
    def partial_success_after_transaction(self) -> bool:
        """Transaction phase committed but finalize did not complete successfully."""
        return self.transaction_committed and not self.finalize_succeeded


@dataclass(frozen=True)
class RenameContext:
    """Read-only inputs for building a rename plan."""

    old_name: str
    new_name: str
    transcript_path: str
    transcript_file: Path
    new_transcript_path: Path
    old_output_dir: Path
    new_output_dir: Path


@dataclass(frozen=True)
class RenamePlanValidation:
    """One read-only pre-transaction check recorded on the plan."""

    name: str
    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class ProcessingStateRenameMutation:
    """Computed processing_state row update (apply via ``_persist_processing_state_mutation``)."""

    entry_key: str
    enriched_entry: dict[str, Any]
    sibling_path_validation_msgs: tuple[str, ...] = ()


@dataclass
class RenamePlan:
    """Ordered rename work: validations, transaction ops, finalize ops, cache targets."""

    blocked: bool = False
    block_message: str = ""
    validations: tuple[RenamePlanValidation, ...] = ()
    warnings: list[str] = field(default_factory=list)
    transaction_file_renames: list[tuple[Path, Path, str]] = field(default_factory=list)
    transaction_state_updates: list[
        tuple[Callable[..., None], tuple[Any, ...], dict[str, Any]]
    ] = field(default_factory=list)
    needs_output_finalize: bool = False
    finalize_ops: tuple[str, ...] = ()
    old_output_dir: Path = field(default_factory=Path)
    new_output_dir: Path = field(default_factory=Path)
    old_name: str = ""
    new_name: str = ""
    transcript_path_before: str = ""
    transcript_path_after: str = ""
    cache_invalidation_targets: tuple[str, str] = ("", "")


def ordered_audio_candidate_paths_for_state_entry(
    file_key: str,
    metadata: dict,
    transcript_path: str,
    *,
    resolved_audio_from_transcript: Optional[str],
    transcript_base: str,
    canonical_base_from_metadata: str,
    base_without_suffix: str,
    recordings_dirs: tuple[Path, ...],
    audio_extensions: tuple[str, ...],
) -> list[str]:
    """
    Ordered candidate path strings for one processing_state row (no existence checks).

    Selection of the first existing path is done by the caller. Order matches
    historical find_original_audio_file behavior for this entry.
    """
    out: list[str] = []

    def _add(raw: str | Path | None) -> None:
        if raw is None:
            return
        s = str(Path(raw))
        if s and s not in out:
            out.append(s)

    if metadata.get("audio_path"):
        _add(metadata["audio_path"])
    if not _looks_like_uuid(file_key):
        _add(file_key)
    if metadata.get("mp3_path"):
        _add(metadata["mp3_path"])
    convert_step = metadata.get("convert", {})
    if isinstance(convert_step, dict):
        step_mp3 = convert_step.get("mp3_path")
        if step_mp3:
            _add(step_mp3)
    steps = metadata.get("steps", {})
    if isinstance(steps, dict):
        legacy_convert = steps.get("convert", {})
        if isinstance(legacy_convert, dict):
            legacy_step_mp3 = legacy_convert.get("mp3_path")
            if legacy_step_mp3:
                _add(legacy_step_mp3)
    if resolved_audio_from_transcript:
        _add(resolved_audio_from_transcript)
    for s in _build_audio_candidates_from_recordings(
        _audio_lookup_bases(
            canonical_base_from_metadata, transcript_base, base_without_suffix
        ),
        recordings_dirs,
        audio_extensions,
    ):
        _add(s)
    return out


def _fallback_audio_candidate_paths_no_state(
    transcript_path: str,
    *,
    resolved_full: Optional[str],
    resolved_stripped: Optional[str],
    transcript_base: str,
    base_without_suffix: str,
    recordings_dirs: tuple[Path, ...],
    audio_extensions: tuple[str, ...],
) -> list[str]:
    """Ordered candidates when no processing_state row matched (strings only)."""
    out: list[str] = []

    def _add(raw: str | Path | None) -> None:
        if raw is None:
            return
        s = str(Path(raw))
        if s and s not in out:
            out.append(s)

    if resolved_full:
        _add(resolved_full)
    if resolved_stripped:
        _add(resolved_stripped)
    for s in _build_audio_candidates_from_recordings(
        _audio_lookup_bases(transcript_base, base_without_suffix),
        recordings_dirs,
        audio_extensions,
    ):
        _add(s)
    return out


def _audio_lookup_bases(*parts: Optional[str]) -> list[str]:
    """Ordered unique stems for recordings-side audio lookup, including de-duplicated stems."""
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        if not p:
            continue
        for b in (p, strip_duplicate_filename_suffix(p)):
            if b and b not in seen:
                seen.add(b)
                out.append(b)
    return out


def _looks_like_uuid(key: str) -> bool:
    """Return True if key looks like a UUID (e.g. state uses UUID-based keys)."""
    if not key or len(key) != 36:
        return False
    parts = key.split("-")
    return (
        len(parts) == 5
        and len(parts[0]) == 8
        and len(parts[1]) == 4
        and len(parts[2]) == 4
        and len(parts[3]) == 4
        and len(parts[4]) == 12
        and all(p.isalnum() for p in parts)
    )


def _build_audio_candidates_from_recordings(
    bases_sequence: list[str],
    recordings_dirs: tuple[Path, ...],
    audio_extensions: tuple[str, ...],
) -> list[str]:
    """Ordered deduplicated path strings for stems under recordings roots (no I/O)."""
    out: list[str] = []

    def _add(raw: str | Path | None) -> None:
        if raw is None:
            return
        s = str(Path(raw))
        if s and s not in out:
            out.append(s)

    for base in bases_sequence:
        for dir_path in recordings_dirs:
            for ext in audio_extensions:
                _add(dir_path / f"{base}{ext}")
    return out


def extract_date_prefix_from_filename(filename: str) -> str:
    """
    Extract date prefix (YYMMDD_) from filename.

    Attempts to extract YYMMDD from filenames in format YYYYMMDDHHMMSS or similar patterns.
    For example: "20251230160235.wav" -> "251230_"

    Args:
        filename: Filename (with or without extension)

    Returns:
        Date prefix string in format YYMMDD_ (e.g., "251230_"), or empty string if not found
    """
    try:
        # Remove extension if present
        stem = Path(filename).stem

        # Try to match YYYYMMDDHHMMSS pattern (14 digits)
        if len(stem) >= 8 and stem[:8].isdigit():
            year = stem[:4]
            month = stem[4:6]
            day = stem[6:8]

            # Validate date components
            if int(month) in range(1, 13) and int(day) in range(1, 32):
                # Extract YYMMDD from YYYYMMDD
                yy = year[2:4]  # Last 2 digits of year
                date_prefix = f"{yy}{month}{day}_"
                return date_prefix

        # Try to match YYMMDD pattern at the start (6 digits followed by underscore or end)
        if len(stem) >= 6 and stem[:6].isdigit():
            yy = stem[:2]
            mm = stem[2:4]
            dd = stem[4:6]

            # Validate date components
            if int(mm) in range(1, 13) and int(dd) in range(1, 32):
                date_prefix = f"{yy}{mm}{dd}_"
                return date_prefix

        return ""
    except (ValueError, IndexError):
        return ""


def extract_date_prefix(audio_file_path: Path) -> str:
    """
    Extract date prefix (YYMMDD_) from audio file.

    First attempts to extract from filename, then falls back to file modification time.

    Args:
        audio_file_path: Path to the audio file

    Returns:
        Date prefix string in format YYMMDD_ (e.g., "251216_")
    """
    try:
        # First, try to extract from filename
        date_prefix = extract_date_prefix_from_filename(audio_file_path.name)
        if date_prefix:
            return date_prefix

        # Fallback to modification time if filename extraction fails
        if not audio_file_path.exists():
            logger.warning(f"Audio file not found: {audio_file_path}")
            return ""

        # Get modification time
        mtime = audio_file_path.stat().st_mtime
        dt = datetime.fromtimestamp(mtime)

        # Format as YYMMDD_
        date_prefix = dt.strftime("%y%m%d_")
        return date_prefix
    except Exception as e:
        log_error(
            "FILE_RENAME",
            f"Error extracting date from {audio_file_path}: {e}",
            exception=e,
        )
        return ""


def extract_date_prefix_from_transcript(transcript_path: str | Path) -> str:
    """
    Extract date prefix (YYMMDD_) from transcript file.

    First attempts to extract from filename, then falls back to file modification time.

    Args:
        transcript_path: Path to the transcript JSON file

    Returns:
        Date prefix string in format YYMMDD_ (e.g., "251216_"), or empty string if not found
    """
    try:
        transcript_file = Path(transcript_path)

        date_prefix = extract_date_prefix_from_filename(transcript_file.name)
        if date_prefix:
            return date_prefix

        if not transcript_file.exists():
            logger.info(
                f"Transcript file not found for date extraction: {transcript_path}"
            )
            return ""

        mtime = transcript_file.stat().st_mtime
        dt = datetime.fromtimestamp(mtime)
        return dt.strftime("%y%m%d_")
    except Exception as e:
        log_error(
            "FILE_RENAME",
            f"Error extracting date from transcript {transcript_path}: {e}",
            exception=e,
        )
        return ""


def find_original_audio_file(transcript_path: str) -> Optional[Path]:
    """
    Find original audio file path from transcript path.

    First checks processing_state.json for entries matching the transcript path.
    If not found, tries to infer from transcript name or file modification time.

    Args:
        transcript_path: Path to the transcript JSON file

    Returns:
        Path to original audio file if found, None otherwise
    """
    try:
        recordings_dirs_tpl = (RECORDINGS_DIR, OUTPUTS_DIR / "recordings")
        exts_tpl = (".wav", ".mp3", ".m4a", ".flac", ".aac", ".ogg")

        def _first_existing(candidates: list[str]) -> Optional[Path]:
            for s in candidates:
                p = Path(s)
                if p.exists():
                    return p
            return None

        if PROCESSING_STATE_FILE.exists():
            with open(PROCESSING_STATE_FILE, "r") as f:
                state = json.load(f)

            processed_files = state.get("processed_files", {})

            for file_key, metadata in processed_files.items():
                if not isinstance(metadata, dict):
                    continue
                if metadata.get("transcript_path") != transcript_path:
                    continue

                resolved_audio: Optional[str] = None
                try:
                    resolved_audio = str(
                        resolve_file_path(
                            transcript_path,
                            file_type="audio",
                            validate_state=False,
                        )
                    )
                except FileNotFoundError:
                    resolved_audio = None

                transcript_base = get_base_name(transcript_path)
                canonical_base = metadata.get("canonical_base_name") or transcript_base
                base_without_suffix = (
                    transcript_base.rsplit("_", 1)[0]
                    if "_" in transcript_base
                    else transcript_base
                )

                candidate_strings = ordered_audio_candidate_paths_for_state_entry(
                    str(file_key),
                    metadata,
                    transcript_path,
                    resolved_audio_from_transcript=resolved_audio,
                    transcript_base=transcript_base,
                    canonical_base_from_metadata=str(canonical_base),
                    base_without_suffix=base_without_suffix,
                    recordings_dirs=recordings_dirs_tpl,
                    audio_extensions=exts_tpl,
                )
                hit = _first_existing(candidate_strings)
                if hit is not None:
                    return hit

                path_ref = metadata.get("audio_path") or (
                    file_key if not _looks_like_uuid(str(file_key)) else None
                )
                logger.info(
                    "Original audio file from state not found; "
                    f"speaker identification will continue without playback: {path_ref or file_key}"
                )

        transcript_base = get_base_name(transcript_path)
        base_without_suffix = (
            transcript_base.rsplit("_", 1)[0]
            if "_" in transcript_base
            else transcript_base
        )
        resolved_full: Optional[str] = None
        try:
            resolved_full = str(
                resolve_file_path(
                    transcript_path, file_type="audio", validate_state=False
                )
            )
        except FileNotFoundError:
            pass
        resolved_stripped: Optional[str] = None
        try:
            resolved_stripped = str(
                resolve_file_path(
                    base_without_suffix,
                    file_type="audio",
                    validate_state=False,
                )
            )
        except FileNotFoundError:
            pass

        fallback = _fallback_audio_candidate_paths_no_state(
            transcript_path,
            resolved_full=resolved_full,
            resolved_stripped=resolved_stripped,
            transcript_base=transcript_base,
            base_without_suffix=base_without_suffix,
            recordings_dirs=recordings_dirs_tpl,
            audio_extensions=exts_tpl,
        )
        hit = _first_existing(fallback)
        if hit is not None:
            return hit

    except Exception as e:
        log_error("FILE_RENAME", f"Error finding original audio file: {e}", exception=e)

    return None


def _legacy_rename_hook_noop(old_path: str, new_path: str) -> None:
    """No-op retained for compatibility after legacy path-state removal."""
    return


def _mutate_metadata_for_rename(
    metadata: dict,
    old_path: str,
    new_path: str,
    old_name: str,
    new_name: str,
) -> None:
    """Apply path rewrites for a rename onto a metadata dict (mutates in place)."""
    from transcriptx.core.utils.processing_state import same_resolved_path

    old_canonical_base = get_canonical_base_name(old_path)
    new_canonical_base = get_canonical_base_name(new_path)
    new_output_dir = OUTPUTS_DIR / new_canonical_base
    new_path_str = str(new_path)

    metadata["transcript_path"] = new_path_str
    metadata["current_transcript_path"] = new_path_str

    mp3_path = metadata.get("mp3_path", "")
    old_mp3_path = mp3_path
    if mp3_path and old_name in mp3_path:
        new_mp3_path = mp3_path.replace(old_name, new_name)
        metadata["mp3_path"] = new_mp3_path
    elif mp3_path:
        old_mp3_base = get_canonical_base_name(mp3_path)
        if old_mp3_base == old_canonical_base:
            mp3_dir = Path(mp3_path).parent
            mp3_ext = Path(mp3_path).suffix
            new_mp3_path = str(mp3_dir / f"{new_name}{mp3_ext}")
            metadata["mp3_path"] = new_mp3_path
            old_mp3_path = mp3_path

    metadata["output_dir_path"] = str(new_output_dir)
    metadata["canonical_base_name"] = new_canonical_base

    steps = metadata.get("steps", {})
    if steps:
        if "transcribe" in steps:
            transcribe_step = steps["transcribe"]
            step_tp = transcribe_step.get("transcript_path")
            if same_resolved_path(step_tp, old_path):
                transcribe_step["transcript_path"] = new_path_str
            elif step_tp:
                step_transcript_base = get_canonical_base_name(step_tp)
                if step_transcript_base == old_canonical_base:
                    step_transcript_dir = Path(step_tp).parent
                    transcribe_step["transcript_path"] = str(
                        step_transcript_dir / f"{new_name}.json"
                    )

        if "convert" in steps:
            convert_step = steps["convert"]
            step_mp3 = convert_step.get("mp3_path")
            if old_mp3_path and step_mp3 == old_mp3_path:
                convert_step["mp3_path"] = metadata.get("mp3_path", old_mp3_path)
            elif step_mp3:
                step_mp3_base = get_canonical_base_name(step_mp3)
                if step_mp3_base == old_canonical_base:
                    step_mp3_dir = Path(step_mp3).parent
                    step_mp3_ext = Path(step_mp3).suffix
                    convert_step["mp3_path"] = str(
                        step_mp3_dir / f"{new_name}{step_mp3_ext}"
                    )

    transcribe_step = metadata.get("transcribe")
    if isinstance(transcribe_step, dict):
        step_tp = transcribe_step.get("transcript_path")
        if same_resolved_path(step_tp, old_path):
            transcribe_step["transcript_path"] = new_path_str
        elif step_tp:
            step_transcript_base = get_canonical_base_name(step_tp)
            if step_transcript_base == old_canonical_base:
                step_transcript_dir = Path(step_tp).parent
                transcribe_step["transcript_path"] = str(
                    step_transcript_dir / f"{new_name}.json"
                )

    convert_step = metadata.get("convert")
    if isinstance(convert_step, dict):
        step_mp3 = convert_step.get("mp3_path")
        if old_mp3_path and step_mp3 == old_mp3_path:
            convert_step["mp3_path"] = metadata.get("mp3_path", old_mp3_path)
        elif step_mp3:
            step_mp3_base = get_canonical_base_name(step_mp3)
            if step_mp3_base == old_canonical_base:
                step_mp3_dir = Path(step_mp3).parent
                step_mp3_ext = Path(step_mp3).suffix
                convert_step["mp3_path"] = str(
                    step_mp3_dir / f"{new_name}{step_mp3_ext}"
                )

    metadata["last_updated"] = datetime.now().isoformat()


def _build_enriched_entry_for_rename(
    metadata: dict,
    old_path: str,
    new_path: str,
    old_name: str,
    new_name: str,
    new_path_str: str,
) -> dict:
    """Return enriched processing_state row for ``new_path_str`` (pure aside from imports)."""
    from transcriptx.core.utils.state_schema import enrich_state_entry

    work = copy.deepcopy(metadata)
    _mutate_metadata_for_rename(work, old_path, new_path, old_name, new_name)
    return enrich_state_entry(work, new_path_str)


def _sibling_path_validation_messages(
    processed_files: dict, new_path_str: str
) -> list[str]:
    """Human-readable messages for state rows tied to ``new_path_str`` with invalid paths."""
    from transcriptx.core.utils.state_schema import validate_state_paths
    from transcriptx.core.utils.processing_state import same_resolved_path

    msgs: list[str] = []
    for _ek, em in processed_files.items():
        tp = em.get("transcript_path") if isinstance(em, dict) else None
        if tp and same_resolved_path(tp, new_path_str):
            is_valid, errors = validate_state_paths(em)
            if not is_valid:
                msgs.append(f"State entry has invalid paths after update: {errors!r}")
    return msgs


def _compute_processing_state_rename_mutation(
    state: dict,
    old_path: str,
    new_path: str,
    old_name: str,
    new_name: str,
) -> Optional[ProcessingStateRenameMutation]:
    """Compute the updated row and sibling validation messages (no disk write)."""
    from transcriptx.core.utils.processing_state import find_processed_entry_for_path

    processed_files = state.get("processed_files", {})
    if not isinstance(processed_files, dict):
        return None

    key, metadata = find_processed_entry_for_path(old_path, state)
    if metadata is None or key is None:
        return None

    new_path_str = str(new_path)
    enriched = _build_enriched_entry_for_rename(
        metadata, old_path, new_path, old_name, new_name, new_path_str
    )
    temp_processed = dict(processed_files)
    temp_processed[key] = enriched
    sibling_msgs = tuple(
        _sibling_path_validation_messages(temp_processed, new_path_str)
    )
    return ProcessingStateRenameMutation(
        entry_key=str(key),
        enriched_entry=enriched,
        sibling_path_validation_msgs=sibling_msgs,
    )


def _persist_processing_state_mutation(
    state: dict, mutation: ProcessingStateRenameMutation, state_file: Path
) -> None:
    """Apply mutation to ``state`` and persist to ``state_file``."""
    from transcriptx.core.utils.processing_state import save_processing_state

    processed = state.setdefault("processed_files", {})
    processed[mutation.entry_key] = mutation.enriched_entry
    for msg in mutation.sibling_path_validation_msgs:
        logger.warning("%s", msg)
    save_processing_state(state, state_file)


def update_processing_state(
    old_path: str, new_path: str, old_name: str, new_name: str
) -> None:
    """Update processing_state.json to reflect renamed files.

    With UUID-based keys, this is much simpler - we only update metadata fields
    and do not touch the keys themselves.

    Updates all path references including:
    - transcript_path
    - mp3_path
    - output_dir_path
    - canonical_base_name
    - last_updated timestamp
    - Step-level paths for both legacy (steps.transcribe/convert) and current
      top-level structure (transcribe/convert).

    Args:
        old_path: Old transcript path
        new_path: New transcript path
        old_name: Old base name
        new_name: New base name
    """
    try:
        if not PROCESSING_STATE_FILE.exists():
            return

        with open(PROCESSING_STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)

        mutation = _compute_processing_state_rename_mutation(
            state, old_path, new_path, old_name, new_name
        )
        if mutation is None:
            logger.warning(
                "No processing state entry matched rename source path %s; state not updated",
                old_path,
            )
            return

        _persist_processing_state_mutation(state, mutation, PROCESSING_STATE_FILE)
        logger.info("Updated processing_state.json with new paths")

    except Exception as e:
        log_error("FILE_RENAME", f"Error updating processing state: {e}", exception=e)


def rename_files_in_directory(
    old_dir: Path, new_dir: Path, old_name: str, new_name: str
) -> list[str]:
    """
    Rename files inside a directory that contain the old name.

    Args:
        old_dir: Old directory path
        new_dir: New directory path
        old_name: Old base name
        new_name: New base name

    Returns:
        Non-fatal warning strings (per-file failures or outer exceptions).
    """
    warnings: list[str] = []
    if not new_dir.exists():
        return warnings

    try:
        for file_path in new_dir.rglob("*"):
            if file_path.is_file():
                old_filename = file_path.name
                if old_name in old_filename:
                    new_filename = old_filename.replace(old_name, new_name)
                    new_file_path = file_path.parent / new_filename
                    if new_file_path != file_path:
                        try:
                            file_path.rename(new_file_path)
                            logger.debug(
                                "Renamed file: %s -> %s", old_filename, new_filename
                            )
                        except OSError as err:
                            warnings.append(
                                f"Could not rename {file_path} -> {new_file_path}: {err}"
                            )
    except Exception as e:
        log_error("FILE_RENAME", f"Error renaming files in directory: {e}", exception=e)
        warnings.append(f"rename_files_in_directory: {e}")
    return warnings


def build_rename_plan(
    ctx: RenameContext,
    state_snapshot: Optional[dict],
    rename_history_at_iso: str,
) -> RenamePlan:
    """
    Build a deterministic rename plan (read-only: no filesystem mutations).

    Caller supplies ``state_snapshot`` from a prior read of processing state
    (or None when no file exists). Pass ``rename_history_at_iso`` from the
    orchestrator so the plan does not embed wall-clock reads.
    """
    transcript_file = ctx.transcript_file
    new_transcript_path = ctx.new_transcript_path
    old_transcript_dir = ctx.old_output_dir
    new_transcript_dir = ctx.new_output_dir
    old_name = ctx.old_name
    new_name = ctx.new_name
    transcript_path = ctx.transcript_path

    vals: list[RenamePlanValidation] = []

    if not transcript_file.exists():
        vals.append(
            RenamePlanValidation("transcript_file_exists", False, str(transcript_path))
        )
        return RenamePlan(
            blocked=True,
            block_message=f"Transcript file not found: {transcript_path}",
            validations=tuple(vals),
        )
    vals.append(
        RenamePlanValidation("transcript_file_exists", True, str(transcript_file))
    )

    managed_validation = validate_managed_transcript(transcript_file)
    if not managed_validation.ok:
        vals.append(
            RenamePlanValidation(
                "managed_library_transcript",
                False,
                managed_validation.message
                or "transcript is not library-valid managed transcript",
            )
        )
        return RenamePlan(
            blocked=True,
            block_message=managed_validation.message
            or "transcript is not library-valid managed transcript",
            validations=tuple(vals),
        )
    vals.append(RenamePlanValidation("managed_library_transcript", True, ""))

    plan_warnings: list[str] = list(managed_validation.warnings or [])

    if new_transcript_path.exists() and new_transcript_path != transcript_file:
        vals.append(
            RenamePlanValidation(
                "target_transcript_path_available",
                False,
                str(new_transcript_path),
            )
        )
        return RenamePlan(
            blocked=True,
            block_message=f"Rename blocked: file already exists: {new_transcript_path}",
            validations=tuple(vals),
        )
    vals.append(RenamePlanValidation("target_transcript_path_available", True, ""))

    if new_transcript_dir.exists() and new_transcript_dir != old_transcript_dir:
        vals.append(
            RenamePlanValidation(
                "target_output_dir_available",
                False,
                str(new_transcript_dir),
            )
        )
        return RenamePlan(
            blocked=True,
            block_message=(
                f"Rename blocked: output directory already exists: {new_transcript_dir}"
            ),
            validations=tuple(vals),
        )
    vals.append(RenamePlanValidation("target_output_dir_available", True, ""))

    transaction_file_renames: list[tuple[Path, Path, str]] = []
    if transcript_file != new_transcript_path:
        transaction_file_renames.append(
            (
                transcript_file,
                new_transcript_path,
                f"Rename transcript: {old_name} -> {new_name}",
            )
        )

    old_sidecar = sidecar_path_for(transcript_file)
    new_sidecar = sidecar_path_for(new_transcript_path)
    if old_sidecar.exists() and old_sidecar != new_sidecar:
        transaction_file_renames.append(
            (
                old_sidecar,
                new_sidecar,
                f"Rename speaker map sidecar: {old_sidecar.name} -> {new_sidecar.name}",
            )
        )

    old_import_meta_sidecar = import_meta_sidecar_path_for_transcript(transcript_file)
    new_import_meta_sidecar = import_meta_sidecar_path_for_transcript(
        new_transcript_path
    )
    if not old_import_meta_sidecar.exists():
        vals.append(
            RenamePlanValidation(
                "import_metadata_sidecar_present",
                False,
                str(old_import_meta_sidecar),
            )
        )
        return RenamePlan(
            blocked=True,
            block_message=(
                f"Rename blocked: managed import sidecar missing: {old_import_meta_sidecar}"
            ),
            validations=tuple(vals),
        )
    vals.append(
        RenamePlanValidation(
            "import_metadata_sidecar_present", True, str(old_import_meta_sidecar)
        )
    )

    if old_import_meta_sidecar != new_import_meta_sidecar:
        if new_import_meta_sidecar.exists():
            vals.append(
                RenamePlanValidation(
                    "import_metadata_sidecar_target_available",
                    False,
                    str(new_import_meta_sidecar),
                )
            )
            return RenamePlan(
                blocked=True,
                block_message=(
                    "Rename blocked: target import sidecar already exists: "
                    f"{new_import_meta_sidecar}"
                ),
                validations=tuple(vals),
            )
        vals.append(
            RenamePlanValidation("import_metadata_sidecar_target_available", True, "")
        )
        transaction_file_renames.append(
            (
                old_import_meta_sidecar,
                new_import_meta_sidecar,
                (
                    "Rename managed import sidecar: "
                    f"{old_import_meta_sidecar.name} -> {new_import_meta_sidecar.name}"
                ),
            )
        )
    else:
        vals.append(
            RenamePlanValidation(
                "import_metadata_sidecar_target_available", True, "unchanged"
            )
        )

    old_audio_file: Optional[Path] = None
    new_audio_file: Optional[Path] = None
    if state_snapshot:
        try:
            from transcriptx.core.utils.processing_state import (
                find_processed_entry_for_path,
            )

            _, metadata = find_processed_entry_for_path(
                str(transcript_path), state_snapshot
            )
            if metadata:
                mp3_path = metadata.get("mp3_path", "")
                if mp3_path:
                    cand = Path(mp3_path)
                    if cand.exists():
                        old_audio_file = cand
                        new_audio_file = cand.parent / f"{new_name}{cand.suffix}"
        except Exception as e:
            logger.debug("Could not use processing state for MP3 rename: %s", e)

    if not old_audio_file or not old_audio_file.exists():
        for ext in (".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"):
            candidate = RECORDINGS_DIR / f"{old_name}{ext}"
            if candidate.exists():
                old_audio_file = candidate
                new_audio_file = RECORDINGS_DIR / f"{new_name}{ext}"
                break

    if (
        old_audio_file
        and old_audio_file.exists()
        and new_audio_file is not None
        and not new_audio_file.exists()
    ):
        transaction_file_renames.append(
            (
                old_audio_file,
                new_audio_file,
                f"Rename audio file: {old_audio_file.name} -> {new_audio_file.name}",
            )
        )

    transaction_state_updates: list[
        tuple[Callable[..., None], tuple[Any, ...], dict[str, Any]]
    ] = [
        (
            update_processing_state,
            (str(transcript_path), str(new_transcript_path), old_name, new_name),
            {},
        ),
        (
            append_rename_history,
            (),
            {
                "sidecar_path": str(new_import_meta_sidecar),
                "old_filename": f"{old_name}.json",
                "new_filename": f"{new_name}.json",
                "at_iso": rename_history_at_iso,
            },
        ),
    ]

    needs_finalize = (
        old_transcript_dir.exists() and old_transcript_dir != new_transcript_dir
    )
    finalize_ops: tuple[str, ...] = (
        ("output_dir_merge", "rename_files_in_directory") if needs_finalize else ()
    )
    cache_before, cache_after = str(transcript_path), str(new_transcript_path)

    vals.append(RenamePlanValidation("rename_plan_complete", True, ""))

    return RenamePlan(
        blocked=False,
        validations=tuple(vals),
        warnings=plan_warnings,
        transaction_file_renames=transaction_file_renames,
        transaction_state_updates=transaction_state_updates,
        needs_output_finalize=needs_finalize,
        finalize_ops=finalize_ops,
        old_output_dir=old_transcript_dir,
        new_output_dir=new_transcript_dir,
        old_name=old_name,
        new_name=new_name,
        transcript_path_before=cache_before,
        transcript_path_after=cache_after,
        cache_invalidation_targets=(cache_before, cache_after),
    )


def _finalize_output_directory_move(old_dir: Path, new_dir: Path) -> None:
    """Best-effort merge/move of transcript output directory (non-transactional)."""
    if not old_dir.exists() or old_dir == new_dir:
        return
    if not new_dir.exists():
        new_dir.mkdir(parents=True, exist_ok=True)
    for item in old_dir.iterdir():
        dest = new_dir / item.name
        if dest.exists():
            if item.is_dir():
                for subitem in item.rglob("*"):
                    rel_path = subitem.relative_to(item)
                    new_subitem = dest / rel_path
                    new_subitem.parent.mkdir(parents=True, exist_ok=True)
                    if subitem.is_file():
                        shutil.move(str(subitem), str(new_subitem))
            else:
                logger.warning("Skipping %s - already exists in destination", item.name)
        else:
            shutil.move(str(item), str(dest))
    try:
        if old_dir.exists() and not any(old_dir.iterdir()):
            old_dir.rmdir()
    except OSError:
        pass
    logger.info("Renamed output directory: %s -> %s", old_dir.name, new_dir.name)


def rename_transcript_files_with_outcome(
    old_name: str, new_name: str, transcript_path: str, dry_run: bool = False
) -> RenameTranscriptOutcome:
    """
    Rename transcript and related artifacts; return structured outcome.

    Transaction phase: file renames + processing_state + rename_history (rollback-capable).
    Finalize phase: output directory merge/move + in-tree filename fixes (best-effort).
    """
    warnings: list[str] = []
    try:
        transcript_file = Path(transcript_path)
        old_transcript_dir = Path(get_transcript_dir(transcript_path))
        new_transcript_path = transcript_file.parent / f"{new_name}.json"
        new_transcript_dir = Path(get_transcript_dir(str(new_transcript_path)))

        state_snapshot: Optional[dict] = None
        if PROCESSING_STATE_FILE.exists():
            with open(PROCESSING_STATE_FILE, "r", encoding="utf-8") as handle:
                state_snapshot = json.load(handle)

        rename_history_at_iso = datetime.now().isoformat()
        ctx = RenameContext(
            old_name=old_name,
            new_name=new_name,
            transcript_path=transcript_path,
            transcript_file=transcript_file,
            new_transcript_path=new_transcript_path,
            old_output_dir=old_transcript_dir,
            new_output_dir=new_transcript_dir,
        )
        plan = build_rename_plan(ctx, state_snapshot, rename_history_at_iso)
        if plan.blocked:
            msg = plan.block_message or "rename blocked"
            logger.error("%s", msg)
            return RenameTranscriptOutcome(
                transaction_attempted=False,
                transaction_succeeded=False,
                transaction_committed=False,
                finalize_attempted=False,
                finalize_succeeded=False,
                warnings=warnings,
                last_error=msg,
            )

        warnings.extend(plan.warnings)

        if dry_run:
            logger.info("DRY RUN: Would rename %s -> %s", old_name, new_name)

        transaction = RenameTransaction(dry_run=dry_run)
        for src, dest, desc in plan.transaction_file_renames:
            transaction.add_rename(src, dest, desc)
        for func, args, kwargs in plan.transaction_state_updates:
            transaction.add_state_update(func, *args, **kwargs)

        transaction_attempted = True
        if not transaction.execute():
            logger.error("Rename transaction failed; changes rolled back")
            return RenameTranscriptOutcome(
                transaction_attempted=transaction_attempted,
                transaction_succeeded=False,
                transaction_committed=False,
                finalize_attempted=False,
                finalize_succeeded=False,
                warnings=warnings,
                last_error="rename transaction failed",
            )

        if dry_run:
            return RenameTranscriptOutcome(
                transaction_attempted=True,
                transaction_succeeded=True,
                transaction_committed=False,
                finalize_attempted=False,
                finalize_succeeded=True,
                warnings=warnings,
            )

        finalize_attempted = plan.needs_output_finalize
        finalize_succeeded = True
        if plan.needs_output_finalize:
            try:
                _finalize_output_directory_move(
                    plan.old_output_dir, plan.new_output_dir
                )
            except Exception as e:
                logger.error("Error renaming output directory: %s", e)
                logger.error(
                    "Rename transaction phase already committed (transcript, state, "
                    "history). Not rolling back — finalize is a separate boundary; "
                    "output tree may be partially moved. Investigate %s -> %s",
                    plan.old_output_dir,
                    plan.new_output_dir,
                )
                finalize_succeeded = False
                warnings.append(
                    "Output directory finalize failed after the rename transaction "
                    "committed; transcript and processing_state already reflect the new "
                    "name. Check output folders for a partial merge."
                )
                return RenameTranscriptOutcome(
                    transaction_attempted=True,
                    transaction_succeeded=True,
                    transaction_committed=True,
                    finalize_attempted=True,
                    finalize_succeeded=False,
                    warnings=warnings,
                    last_error=str(e),
                )

        if plan.new_output_dir.exists():
            dir_warnings = rename_files_in_directory(
                plan.old_output_dir,
                plan.new_output_dir,
                plan.old_name,
                plan.new_name,
            )
            warnings.extend(dir_warnings)

        cb, ca = plan.cache_invalidation_targets
        if cb:
            invalidate_path_cache(cb)
        if ca:
            invalidate_path_cache(ca)

        if not dry_run:
            logger.info("Successfully renamed all files: %s -> %s", old_name, new_name)

        return RenameTranscriptOutcome(
            transaction_attempted=True,
            transaction_succeeded=True,
            transaction_committed=True,
            finalize_attempted=finalize_attempted,
            finalize_succeeded=finalize_succeeded,
            warnings=warnings,
        )

    except Exception as e:
        log_error("FILE_RENAME", f"Error renaming transcript files: {e}", exception=e)
        logger.error("Error renaming files: %s", e)
        return RenameTranscriptOutcome(
            transaction_attempted=False,
            transaction_succeeded=False,
            transaction_committed=False,
            finalize_attempted=False,
            finalize_succeeded=False,
            warnings=warnings,
            last_error=str(e),
        )


def rename_transcript_files(
    old_name: str, new_name: str, transcript_path: str, dry_run: bool = False
) -> bool:
    """
    Perform all rename operations atomically with rollback support.

    This function renames:
    - Transcript JSON file
    - Audio file (if exists in recordings directory)
    - Speaker map file
    - Output directory
    - Files inside output directory that contain the old name
    - Updates processing_state.json

    Args:
        old_name: Current base name (without extension)
        new_name: New base name (without extension)
        transcript_path: Current path to transcript file
        dry_run: If True, show what would be done without doing it

    Returns:
        True if rename was successful, False otherwise
    """
    return rename_transcript_files_with_outcome(
        old_name, new_name, transcript_path, dry_run=dry_run
    ).ok


def prompt_for_rename(transcript_path: str, default_name: str) -> Optional[str]:
    """
    Interactive prompt for renaming transcript files.

    Args:
        transcript_path: Current path to transcript file
        default_name: Default name to prefill (should include date prefix)

    Returns:
        New name if user provided one, None if skipped or cancelled
    """
    import questionary
    from rich.console import Console

    console = Console()
    try:
        old_name = get_base_name(transcript_path)

        console.print("\n[bold cyan]📝 Rename Transcript[/bold cyan]")
        console.print(f"[dim]Current name: {old_name}[/dim]")

        prompt_msg = "Enter new name for transcript (or press Enter to skip):"
        new_name = questionary.text(prompt_msg).ask()

        if not new_name or new_name.strip() == "":
            console.print("[yellow]⏭️ Rename skipped[/yellow]")
            return None

        new_name = new_name.strip()

        # Validate name (no invalid characters)
        invalid_chars = ["/", "\\", ":", "*", "?", '"', "<", ">", "|"]
        if any(char in new_name for char in invalid_chars):
            console.print(
                f"[red]❌ Invalid characters in name: {', '.join(invalid_chars)}[/red]"
            )
            return None

        if new_name == old_name:
            console.print("[yellow]⏭️ Name unchanged, skipping rename[/yellow]")
            return None

        # Perform rename
        if rename_transcript_files(old_name, new_name, transcript_path):
            console.print(f"[green]✅ Successfully renamed to: {new_name}[/green]")
            return new_name
        else:
            return None

    except KeyboardInterrupt:
        console.print("\n[yellow]⏭️ Rename cancelled[/yellow]")
        return None
    except Exception as e:
        log_error("FILE_RENAME", f"Error in rename prompt: {e}", exception=e)
        return None


def rename_mp3_file(mp3_path: Path, default_name: str = "") -> Optional[Path]:
    """
    Simple function to rename an MP3 file.

    Args:
        mp3_path: Path to the MP3 file to rename
        default_name: Default name to prefill (without extension)

    Returns:
        New Path if renamed, None if skipped or cancelled
    """
    import questionary
    from rich.console import Console

    console = Console()
    try:
        if not mp3_path.exists():
            logger.warning(f"MP3 file not found: {mp3_path}")
            return None

        old_name = mp3_path.stem

        console.print("\n[bold cyan]📝 Rename MP3 File[/bold cyan]")
        console.print(f"[dim]Current name: {old_name}[/dim]")

        prompt_msg = "Enter new name for MP3 file (or press Enter to skip):"
        new_name = questionary.text(prompt_msg).ask()

        if not new_name or new_name.strip() == "":
            console.print("[yellow]⏭️ Rename skipped[/yellow]")
            return None

        new_name = new_name.strip()

        # Validate name (no invalid characters)
        invalid_chars = ["/", "\\", ":", "*", "?", '"', "<", ">", "|"]
        if any(char in new_name for char in invalid_chars):
            console.print(
                f"[red]❌ Invalid characters in name: {', '.join(invalid_chars)}[/red]"
            )
            return None

        if new_name == old_name:
            console.print("[yellow]⏭️ Name unchanged, skipping rename[/yellow]")
            return None

        # Preserve original extension if user didn't include one
        # Strip trailing dots from user input (e.g., "file." -> "file")
        new_name = new_name.rstrip(".")
        original_extension = mp3_path.suffix
        if original_extension:
            # Check if new_name already has an extension
            new_name_path = Path(new_name)
            if not new_name_path.suffix:
                # No extension in new name, preserve original
                new_name = f"{new_name}{original_extension}"

        # Create new path
        new_path = mp3_path.parent / new_name

        # Check if target already exists
        if new_path.exists() and new_path != mp3_path:
            if not questionary.confirm(
                f"File {new_path.name} already exists. Overwrite?"
            ).ask():
                console.print("[yellow]⏭️ Rename cancelled[/yellow]")
                return None

        # Perform rename
        mp3_path.rename(new_path)
        console.print(f"[green]✅ Successfully renamed to: {new_path.name}[/green]")
        logger.info(f"Renamed MP3 file: {mp3_path.name} -> {new_path.name}")
        return new_path

    except KeyboardInterrupt:
        console.print("\n[yellow]⏭️ Rename cancelled[/yellow]")
        return None
    except Exception as e:
        log_error("FILE_RENAME", f"Error renaming MP3 file: {e}", exception=e)
        console.print(f"[red]❌ Error renaming MP3 file: {e}[/red]")
        return None


def rename_mp3_after_conversion(mp3_path: Path) -> Path:
    """
    Main function to handle renaming MP3 files after conversion.

    This function:
    1. Extracts date prefix from MP3 file metadata
    2. Prompts user to rename with prefilled date prefix
    3. Performs the rename operation

    Args:
        mp3_path: Path to the MP3 file

    Returns:
        New Path if renamed, original Path if skipped or on error
    """
    try:
        # Extract date prefix from MP3 file
        date_prefix = extract_date_prefix(mp3_path)
        default_name = date_prefix if date_prefix else ""

        # Prompt for rename
        new_path = rename_mp3_file(mp3_path, default_name)
        return new_path if new_path else mp3_path

    except Exception as e:
        log_error("FILE_RENAME", f"Error in rename after conversion: {e}", exception=e)
        # Don't raise - this is a non-critical operation
        return mp3_path


def rename_transcript_after_speaker_mapping(transcript_path: str) -> None:
    """
    Main function to handle renaming after speaker mapping is completed.

    This function:
    1. Finds the original audio file
    2. Extracts date prefix from audio file metadata
    3. Prompts user to rename with prefilled date prefix
    4. Performs the rename operation

    Args:
        transcript_path: Path to the transcript file
    """
    try:
        # Find original audio file
        audio_file = find_original_audio_file(transcript_path)

        date_prefix = ""
        if audio_file and audio_file.exists():
            date_prefix = extract_date_prefix(audio_file)

        if not date_prefix:
            date_prefix = extract_date_prefix_from_transcript(transcript_path)

        default_name = date_prefix if date_prefix else ""
        if not default_name:
            logger.info(
                f"No date prefix found for {transcript_path}; using empty default"
            )

        # Prompt for rename
        prompt_for_rename(transcript_path, default_name)

    except Exception as e:
        log_error(
            "FILE_RENAME", f"Error in rename after speaker mapping: {e}", exception=e
        )
        # Don't raise - this is a non-critical operation
