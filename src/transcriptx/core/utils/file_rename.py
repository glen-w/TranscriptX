"""Compatibility re-export shim for managed transcript rename.

All behaviour lives in ``transcriptx.core.utils.rename``. This module preserves
the historical import path ``transcriptx.core.utils.file_rename`` and keeps
monkeypatchable module attributes used by existing tests.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Optional

from transcriptx.core.utils._path_core import get_base_name, get_canonical_base_name
from transcriptx.core.utils._path_resolution import resolve_file_path
from transcriptx.core.utils.logger import get_logger, log_error
from transcriptx.core.utils.paths import (
    OUTPUTS_DIR,
    PROCESSING_STATE_FILE,
    RECORDINGS_DIR,
)
from transcriptx.core.utils.rename.audio_association import (
    _audio_lookup_bases,
    _build_audio_candidates_from_recordings,
    _fallback_audio_candidate_paths_no_state,
    looks_like_uuid as _looks_like_uuid,
    ordered_audio_candidate_paths_for_state_entry,
)
from transcriptx.core.utils.rename.date_prefix import (
    extract_date_prefix_from_filename,
    extract_date_prefix_from_transcript,
)
from transcriptx.core.utils.rename.names import RenameNames
from transcriptx.core.utils.rename.outcome import RenameTranscriptOutcome
from transcriptx.core.utils.rename.pipeline import (
    rename_managed_transcript,
    rename_transcript_files,
    rename_transcript_files_with_outcome,
    repair_managed_rename,
)
from transcriptx.core.utils.rename.plan import (
    ROLLBACK_POLICY,
    RenameContext,
    RenamePlan,
    RenamePlanValidation,
    build_rename_plan,
)
from transcriptx.core.utils.rename.processing_state import (
    ProcessingStateRenameMutation,
    sibling_path_validation_messages as _sibling_path_validation_messages,
    update_processing_state as _update_processing_state_impl,
    compute_processing_state_rename_mutation as _compute_processing_state_rename_mutation_impl,
    persist_processing_state_mutation_strict as _persist_processing_state_mutation_strict,
)
from transcriptx.core.utils.rename_transaction import RenameTransaction
from transcriptx.io.import_metadata_sidecar import (
    append_rename_history,
    validate_managed_transcript,
)

logger = get_logger()


def _persist_processing_state_mutation(state, mutation, state_file):
    """Compat shim: clear warning-era validation msgs before strict persist."""
    if mutation.sibling_path_validation_msgs:
        mutation = ProcessingStateRenameMutation(
            entry_key=mutation.entry_key,
            enriched_entry=mutation.enriched_entry,
            sibling_path_validation_msgs=(),
        )
    return _persist_processing_state_mutation_strict(state, mutation, state_file)


def extract_date_prefix(audio_file_path: Path) -> str:
    """Delegate; uses this module's extract_date_prefix_from_filename / log_error for patches."""
    try:
        date_prefix = extract_date_prefix_from_filename(audio_file_path.name)
        if date_prefix:
            return date_prefix
        if not audio_file_path.exists():
            logger.warning("Audio file not found: %s", audio_file_path)
            return ""
        from datetime import datetime

        mtime = audio_file_path.stat().st_mtime
        return datetime.fromtimestamp(mtime).strftime("%y%m%d_")
    except Exception as e:
        log_error(
            "FILE_RENAME",
            f"Error extracting date from {audio_file_path}: {e}",
            exception=e,
        )
        return ""


def find_original_audio_file(transcript_path: str) -> Optional[Path]:
    """Lookup audio using this module's ``PROCESSING_STATE_FILE`` / dirs (patchable)."""
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
            with open(PROCESSING_STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)

            processed_files = state.get("processed_files", {})
            for file_key, metadata in processed_files.items():
                if not isinstance(metadata, dict):
                    continue
                if metadata.get("transcript_path") != transcript_path:
                    continue

                resolved_audio = None
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

        transcript_base = get_base_name(transcript_path)
        base_without_suffix = (
            transcript_base.rsplit("_", 1)[0]
            if "_" in transcript_base
            else transcript_base
        )
        resolved_full = None
        try:
            resolved_full = str(
                resolve_file_path(
                    transcript_path, file_type="audio", validate_state=False
                )
            )
        except FileNotFoundError:
            pass
        resolved_stripped = None
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
        return _first_existing(fallback)
    except Exception as e:
        log_error("FILE_RENAME", f"Error finding original audio file: {e}", exception=e)
        return None


def prompt_for_rename(transcript_path: str, default_name: str) -> Optional[str]:
    from transcriptx.core.utils.rename import cli as rename_cli

    return rename_cli.prompt_for_rename(transcript_path, default_name)


def rename_transcript_after_speaker_mapping(transcript_path: str) -> None:
    """Uses this module's ``find_original_audio_file`` / ``prompt_for_rename`` (patchable)."""
    try:
        audio_file = find_original_audio_file(transcript_path)
        date_prefix = ""
        if audio_file and audio_file.exists():
            date_prefix = extract_date_prefix(audio_file)
        if not date_prefix:
            date_prefix = extract_date_prefix_from_transcript(transcript_path)
        default_name = date_prefix if date_prefix else ""
        if not default_name:
            logger.info(
                "No date prefix found for %s; using empty default", transcript_path
            )
        prompt_for_rename(transcript_path, default_name)
    except Exception as e:
        log_error(
            "FILE_RENAME",
            f"Error in rename after speaker mapping: {e}",
            exception=e,
        )


def update_processing_state(
    old_path: str, new_path: str, old_name: str, new_name: str
) -> None:
    """Compat: respects monkeypatched ``PROCESSING_STATE_FILE`` on this module."""
    global PROCESSING_STATE_FILE  # noqa: PLW0603 — patch surface
    from transcriptx.core.utils.rename import processing_state as ps

    # Temporarily align package module with this shim's patchable path constant
    prev = ps.PROCESSING_STATE_FILE
    try:
        ps.PROCESSING_STATE_FILE = PROCESSING_STATE_FILE
        _update_processing_state_impl(old_path, new_path, old_name, new_name)
    finally:
        ps.PROCESSING_STATE_FILE = prev


def _mutate_metadata_for_rename(
    metadata: dict,
    old_path: str,
    new_path: str,
    old_name: str,
    new_name: str,
    *,
    rename_timestamp_iso: str | None = None,
    planned_new_audio: str | Path | None = None,
) -> None:
    from datetime import datetime

    from transcriptx.core.utils.rename.names import RenameNames, RenamePaths
    from transcriptx.core.utils.rename.processing_state import (
        mutate_metadata_for_rename,
    )

    old_t = Path(old_path)
    new_t = Path(new_path)
    derived = RenameNames.from_paths(old_t, new_t)
    names = RenameNames(
        old_stem=old_name,
        new_stem=new_name,
        old_canonical=derived.old_canonical,
        new_canonical=derived.new_canonical,
    )
    paths = RenamePaths.from_transcripts(old_t, new_t)
    # Compat: if caller did not pass planned audio but mp3_path basename matches old stem,
    # rewrite to new stem under same parent (exact Path, not substring).
    audio: Path | None
    planned_old: Path | None = None
    if planned_new_audio is not None:
        audio = Path(planned_new_audio)
        mp3 = metadata.get("mp3_path") or ""
        if mp3:
            planned_old = Path(mp3)
    else:
        mp3 = metadata.get("mp3_path") or ""
        audio = None
        if mp3:
            mp3_path = Path(mp3)
            if (
                mp3_path.stem == old_name
                or get_canonical_base_name(mp3) == names.old_canonical
            ):
                planned_old = mp3_path
                audio = mp3_path.parent / f"{new_name}{mp3_path.suffix}"
    mutate_metadata_for_rename(
        metadata,
        names=names,
        paths=paths,
        planned_old_audio=planned_old,
        planned_new_audio=audio,
        rename_timestamp_iso=rename_timestamp_iso or datetime.now().isoformat(),
    )


def _compute_processing_state_rename_mutation(
    state: dict,
    old_path: str,
    new_path: str,
    old_name: str,
    new_name: str,
):
    from datetime import datetime

    from transcriptx.core.utils.rename.names import RenameNames, RenamePaths

    old_t = Path(old_path)
    new_t = Path(new_path)
    derived = RenameNames.from_paths(old_t, new_t)
    names = RenameNames(
        old_stem=old_name,
        new_stem=new_name,
        old_canonical=derived.old_canonical,
        new_canonical=derived.new_canonical,
    )
    paths = RenamePaths.from_transcripts(old_t, new_t)
    return _compute_processing_state_rename_mutation_impl(
        state,
        names=names,
        paths=paths,
        planned_old_audio=None,
        planned_new_audio=None,
        rename_timestamp_iso=datetime.now().isoformat(),
    )


def rename_files_in_directory(
    old_dir: Path, new_dir: Path, old_name: str, new_name: str
) -> list[str]:
    names = RenameNames(
        old_stem=old_name,
        new_stem=new_name,
        old_canonical=old_name,
        new_canonical=new_name,
    )
    from transcriptx.core.utils.rename.finalize import build_artifact_remap_plan

    plan = build_artifact_remap_plan(new_dir, names)
    if plan.blocked:
        return [plan.block_message]
    warnings: list[str] = []
    for source, dest in plan.moves:
        try:
            source.rename(dest)
        except OSError as err:
            warnings.append(f"Could not rename {source} -> {dest}: {err}")
    return warnings


def _finalize_output_directory_move(old_dir: Path, new_dir: Path) -> None:
    from transcriptx.core.utils.rename.finalize import finalize_output_directory_move

    finalize_output_directory_move(old_dir, new_dir)


def _legacy_rename_hook_noop(old_path: str, new_path: str) -> None:
    return None


def rename_mp3_file(mp3_path: Path, default_name: str = "") -> Optional[Path]:
    return None


def rename_mp3_after_conversion(mp3_path: Path) -> Path:
    return Path(mp3_path)


__all__ = [
    "OUTPUTS_DIR",
    "PROCESSING_STATE_FILE",
    "RECORDINGS_DIR",
    "ROLLBACK_POLICY",
    "RenameContext",
    "RenamePlan",
    "RenamePlanValidation",
    "RenameTranscriptOutcome",
    "RenameTransaction",
    "ProcessingStateRenameMutation",
    "append_rename_history",
    "build_rename_plan",
    "extract_date_prefix",
    "extract_date_prefix_from_filename",
    "extract_date_prefix_from_transcript",
    "find_original_audio_file",
    "ordered_audio_candidate_paths_for_state_entry",
    "prompt_for_rename",
    "rename_files_in_directory",
    "rename_managed_transcript",
    "rename_mp3_after_conversion",
    "rename_mp3_file",
    "rename_transcript_after_speaker_mapping",
    "rename_transcript_files",
    "rename_transcript_files_with_outcome",
    "repair_managed_rename",
    "shutil",
    "log_error",
    "resolve_file_path",
    "validate_managed_transcript",
    "update_processing_state",
    "_audio_lookup_bases",
    "_build_audio_candidates_from_recordings",
    "_compute_processing_state_rename_mutation",
    "_fallback_audio_candidate_paths_no_state",
    "_finalize_output_directory_move",
    "_legacy_rename_hook_noop",
    "_looks_like_uuid",
    "_mutate_metadata_for_rename",
    "_persist_processing_state_mutation",
    "_sibling_path_validation_messages",
]
