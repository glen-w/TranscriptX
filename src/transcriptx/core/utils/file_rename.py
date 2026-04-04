"""
File rename utilities for TranscriptX.

This module provides functionality to rename transcript files and their
associated output folders after speaker mapping is completed. The rename
operation updates all related files and references.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

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
        # Load processing state
        if PROCESSING_STATE_FILE.exists():
            with open(PROCESSING_STATE_FILE, "r") as f:
                state = json.load(f)

            processed_files = state.get("processed_files", {})

            # Search for transcript path in processing state
            for file_key, metadata in processed_files.items():
                if metadata.get("transcript_path") != transcript_path:
                    continue
                # State may be keyed by UUID (after migration) or by path; get audio path from metadata first
                audio_path = None
                if metadata.get("audio_path"):
                    audio_path = Path(metadata["audio_path"])
                if audio_path and audio_path.exists():
                    return audio_path
                # Legacy: key may be the original audio path (path-based state)
                if not _looks_like_uuid(file_key):
                    path_candidate = Path(file_key)
                    if path_candidate.exists():
                        return path_candidate
                mp3_path = metadata.get("mp3_path")
                if mp3_path:
                    candidate = Path(mp3_path)
                    if candidate.exists():
                        return candidate
                convert_step = metadata.get("convert", {})
                step_mp3 = convert_step.get("mp3_path")
                if step_mp3:
                    candidate = Path(step_mp3)
                    if candidate.exists():
                        return candidate
                steps = metadata.get("steps", {})
                legacy_convert = steps.get("convert", {})
                legacy_step_mp3 = legacy_convert.get("mp3_path")
                if legacy_step_mp3:
                    candidate = Path(legacy_step_mp3)
                    if candidate.exists():
                        return candidate
                # State had no usable path (e.g. UUID key without audio_path); try resolver/recordings before logging
                try:
                    resolved = resolve_file_path(
                        transcript_path, file_type="audio", validate_state=False
                    )
                    if Path(resolved).exists():
                        return Path(resolved)
                except FileNotFoundError:
                    pass
                # Try recordings: use canonical_base_name from state, then full base, then base without _N suffix
                transcript_base = get_base_name(transcript_path)
                canonical_base = metadata.get("canonical_base_name") or transcript_base
                base_without_suffix = (
                    transcript_base.rsplit("_", 1)[0]
                    if "_" in transcript_base
                    else transcript_base
                )
                recordings_dirs = [
                    RECORDINGS_DIR,
                    OUTPUTS_DIR / "recordings",
                ]
                exts = [".wav", ".mp3", ".m4a", ".flac", ".aac", ".ogg"]
                for base in _audio_lookup_bases(
                    canonical_base, transcript_base, base_without_suffix
                ):
                    for dir_path in recordings_dirs:
                        if not dir_path.exists():
                            continue
                        for ext in exts:
                            candidate = dir_path / f"{base}{ext}"
                            if candidate.exists():
                                return candidate
                # Nothing worked for this entry
                path_ref = metadata.get("audio_path") or (
                    file_key if not _looks_like_uuid(file_key) else None
                )
                logger.info(
                    "Original audio file from state not found; "
                    f"speaker identification will continue without playback: {path_ref or file_key}"
                )

        # If not found in state, try resolver first (handles canonical base matching)
        try:
            resolved = resolve_file_path(
                transcript_path, file_type="audio", validate_state=False
            )
            resolved_path = Path(resolved)
            if resolved_path.exists():
                return resolved_path
        except FileNotFoundError:
            pass

        # If not found in state, try to infer from transcript name
        # Try full base name first (e.g. 260224_CSE), then suffix-stripped (e.g. 260223_team_facilitation from 260223_team_facilitation_8)
        transcript_base = get_base_name(transcript_path)
        base_without_suffix = (
            transcript_base.rsplit("_", 1)[0]
            if "_" in transcript_base
            else transcript_base
        )

        # Try resolver with suffix-stripped base name
        try:
            resolved = resolve_file_path(
                base_without_suffix, file_type="audio", validate_state=False
            )
            resolved_path = Path(resolved)
            if resolved_path.exists():
                return resolved_path
        except FileNotFoundError:
            pass

        # Try common audio extensions: full base first, then base without _N suffix
        audio_extensions = [".wav", ".mp3", ".m4a", ".flac", ".aac", ".ogg"]
        recordings_dirs = [
            RECORDINGS_DIR,
            OUTPUTS_DIR / "recordings",
        ]
        for base in _audio_lookup_bases(transcript_base, base_without_suffix):
            for recordings_dir in recordings_dirs:
                if not recordings_dir.exists():
                    continue
                for ext in audio_extensions:
                    audio_file = recordings_dir / f"{base}{ext}"
                    if audio_file.exists():
                        return audio_file

    except Exception as e:
        log_error("FILE_RENAME", f"Error finding original audio file: {e}", exception=e)

    return None


def _legacy_rename_hook_noop(old_path: str, new_path: str) -> None:
    """No-op retained for compatibility after legacy path-state removal."""
    return


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

        from transcriptx.core.utils.state_schema import (
            enrich_state_entry,
            validate_state_paths,
        )
        from transcriptx.core.utils.processing_state import (
            find_processed_entry_for_path,
            same_resolved_path,
            save_processing_state,
        )

        with open(PROCESSING_STATE_FILE, "r") as f:
            state = json.load(f)

        processed_files = state.get("processed_files", {})

        # Pre-compute canonical bases
        old_canonical_base = get_canonical_base_name(old_path)
        new_canonical_base = get_canonical_base_name(new_path)
        new_output_dir = OUTPUTS_DIR / new_canonical_base

        key, metadata = find_processed_entry_for_path(old_path, state)
        if metadata is None or key is None:
            logger.warning(
                "No processing state entry matched rename source path %s; state not updated",
                old_path,
            )
            return

        new_path_str = str(new_path)

        # Update transcript path (resolved-path matching found the row)
        metadata["transcript_path"] = new_path_str
        metadata["current_transcript_path"] = new_path_str

        # --- mp3_path updates ---
        mp3_path = metadata.get("mp3_path", "")
        old_mp3_path = mp3_path
        if mp3_path and old_name in mp3_path:
            # Simple string replacement when old_name is part of path
            new_mp3_path = mp3_path.replace(old_name, new_name)
            metadata["mp3_path"] = new_mp3_path
        elif mp3_path:
            # Fallback: match by canonical base name
            old_mp3_base = get_canonical_base_name(mp3_path)
            if old_mp3_base == old_canonical_base:
                mp3_dir = Path(mp3_path).parent
                mp3_ext = Path(mp3_path).suffix
                new_mp3_path = str(mp3_dir / f"{new_name}{mp3_ext}")
                metadata["mp3_path"] = new_mp3_path
                old_mp3_path = mp3_path

        # --- high-level metadata paths ---
        metadata["output_dir_path"] = str(new_output_dir)
        metadata["canonical_base_name"] = new_canonical_base

        # --- step-level paths (legacy `steps` structure) ---
        steps = metadata.get("steps", {})
        if steps:
            # transcribe step transcript_path
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

            # convert step mp3_path
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

        # --- step-level paths (current top-level structure) ---
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

        from datetime import datetime

        metadata["last_updated"] = datetime.now().isoformat()

        # Enrich returns a copy — persist back onto the entry
        processed_files[key] = enrich_state_entry(metadata, new_path_str)

        for _ek, em in processed_files.items():
            tp = em.get("transcript_path") if isinstance(em, dict) else None
            if tp and same_resolved_path(tp, new_path_str):
                is_valid, errors = validate_state_paths(em)
                if not is_valid:
                    logger.warning(
                        f"State entry has invalid paths after update: {errors}"
                    )

        save_processing_state(state)
        logger.info("Updated processing_state.json with new paths")

    except Exception as e:
        log_error("FILE_RENAME", f"Error updating processing state: {e}", exception=e)


def rename_files_in_directory(
    old_dir: Path, new_dir: Path, old_name: str, new_name: str
) -> None:
    """
    Rename files inside a directory that contain the old name.

    Args:
        old_dir: Old directory path
        new_dir: New directory path
        old_name: Old base name
        new_name: New base name
    """
    if not new_dir.exists():
        return

    try:
        # Find all files that contain the old name
        for file_path in new_dir.rglob("*"):
            if file_path.is_file():
                old_filename = file_path.name
                if old_name in old_filename:
                    new_filename = old_filename.replace(old_name, new_name)
                    new_file_path = file_path.parent / new_filename
                    if new_file_path != file_path:
                        file_path.rename(new_file_path)
                        logger.debug(f"Renamed file: {old_filename} -> {new_filename}")
    except Exception as e:
        log_error("FILE_RENAME", f"Error renaming files in directory: {e}", exception=e)


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
    transaction = RenameTransaction(dry_run=dry_run)

    try:
        transcript_file = Path(transcript_path)
        if not transcript_file.exists():
            logger.error(f"Transcript file not found: {transcript_path}")
            return False

        managed_validation = validate_managed_transcript(transcript_file)
        if not managed_validation.ok:
            logger.error(
                "Rename blocked: transcript is not library-valid managed transcript: %s",
                managed_validation.message,
            )
            return False

        # Get old paths
        old_transcript_dir = Path(get_transcript_dir(transcript_path))

        # Calculate new paths
        new_transcript_path = transcript_file.parent / f"{new_name}.json"
        new_transcript_dir = OUTPUTS_DIR / new_name

        # Check if new paths would conflict
        if new_transcript_path.exists() and new_transcript_path != transcript_file:
            logger.error("Rename blocked: file already exists: %s", new_transcript_path)
            return False

        if new_transcript_dir.exists() and new_transcript_dir != old_transcript_dir:
            logger.error(
                "Rename blocked: output directory already exists: %s",
                new_transcript_dir,
            )
            return False

        if dry_run:
            logger.info("DRY RUN: Would rename %s -> %s", old_name, new_name)

        # Plan all rename operations in transaction
        # Rename transcript file
        if transcript_file != new_transcript_path:
            transaction.add_rename(
                transcript_file,
                new_transcript_path,
                f"Rename transcript: {old_name} -> {new_name}",
            )

        # Rename speaker-map sidecar alongside the transcript if it exists.
        old_sidecar = sidecar_path_for(transcript_file)
        new_sidecar = sidecar_path_for(new_transcript_path)
        if old_sidecar.exists() and old_sidecar != new_sidecar:
            transaction.add_rename(
                old_sidecar,
                new_sidecar,
                f"Rename speaker map sidecar: {old_sidecar.name} -> {new_sidecar.name}",
            )

        old_import_meta_sidecar = import_meta_sidecar_path_for_transcript(
            transcript_file
        )
        new_import_meta_sidecar = import_meta_sidecar_path_for_transcript(
            new_transcript_path
        )
        if not old_import_meta_sidecar.exists():
            logger.error(
                "Rename blocked: managed import sidecar missing: %s",
                old_import_meta_sidecar,
            )
            return False
        if old_import_meta_sidecar != new_import_meta_sidecar:
            if new_import_meta_sidecar.exists():
                logger.error(
                    "Rename blocked: target import sidecar already exists: %s",
                    new_import_meta_sidecar,
                )
                return False
            transaction.add_rename(
                old_import_meta_sidecar,
                new_import_meta_sidecar,
                (
                    "Rename managed import sidecar: "
                    f"{old_import_meta_sidecar.name} -> {new_import_meta_sidecar.name}"
                ),
            )

        # Find and rename audio file if it exists
        # Use mp3_path from processing state to find actual audio file
        old_audio_file = None
        new_audio_file = None
        if PROCESSING_STATE_FILE.exists():
            try:
                from transcriptx.core.utils.processing_state import (
                    find_processed_entry_for_path,
                )

                with open(PROCESSING_STATE_FILE, "r") as f:
                    state = json.load(f)
                _, metadata = find_processed_entry_for_path(str(transcript_path), state)
                if metadata:
                    mp3_path = metadata.get("mp3_path", "")
                    if mp3_path:
                        old_audio_file = Path(mp3_path)
                        if old_audio_file.exists():
                            mp3_dir = old_audio_file.parent
                            mp3_ext = old_audio_file.suffix
                            new_audio_file = mp3_dir / f"{new_name}{mp3_ext}"
            except Exception as e:
                logger.debug(f"Could not load processing state for MP3 rename: {e}")

        # Fallback: try to find audio file by old_name if not found in state
        if not old_audio_file or not old_audio_file.exists():
            audio_extensions = [".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"]
            for ext in audio_extensions:
                candidate = RECORDINGS_DIR / f"{old_name}{ext}"
                if candidate.exists():
                    old_audio_file = candidate
                    new_audio_file = RECORDINGS_DIR / f"{new_name}{ext}"
                    break

        # Add audio file rename to transaction if found
        if old_audio_file and old_audio_file.exists() and new_audio_file:
            if not new_audio_file.exists():
                transaction.add_rename(
                    old_audio_file,
                    new_audio_file,
                    f"Rename audio file: {old_audio_file.name} -> {new_audio_file.name}",
                )

        # Speaker map sidecars are preserved as part of the transcript artifact set.

        # Rename output directory (handle separately as it's more complex)
        if old_transcript_dir.exists() and old_transcript_dir != new_transcript_dir:
            # This is handled separately as it involves moving multiple files
            # We'll do this after transaction executes
            pass

        # Add state update to transaction
        transaction.add_state_update(
            update_processing_state,
            str(transcript_path),
            str(new_transcript_path),
            old_name,
            new_name,
        )
        transaction.add_state_update(
            append_rename_history,
            sidecar_path=str(new_import_meta_sidecar),
            old_filename=f"{old_name}.json",
            new_filename=f"{new_name}.json",
            at_iso=datetime.now().isoformat(),
        )

        # Execute transaction (all file renames and state update)
        if not transaction.execute():
            logger.error("Rename transaction failed; changes rolled back")
            return False

        # Handle output directory rename (complex operation, do after transaction)
        if old_transcript_dir.exists() and old_transcript_dir != new_transcript_dir:
            try:
                # Move all contents to new directory
                if not new_transcript_dir.exists():
                    new_transcript_dir.mkdir(parents=True, exist_ok=True)

                # Move all files and subdirectories
                for item in old_transcript_dir.iterdir():
                    dest = new_transcript_dir / item.name
                    if dest.exists():
                        # If it's a directory, merge contents
                        if item.is_dir():
                            for subitem in item.rglob("*"):
                                rel_path = subitem.relative_to(item)
                                new_subitem = dest / rel_path
                                new_subitem.parent.mkdir(parents=True, exist_ok=True)
                                if subitem.is_file():
                                    shutil.move(str(subitem), str(new_subitem))
                        else:
                            logger.warning(
                                f"Skipping {item.name} - already exists in destination"
                            )
                    else:
                        shutil.move(str(item), str(dest))

                # Remove old directory if empty
                try:
                    if old_transcript_dir.exists() and not any(
                        old_transcript_dir.iterdir()
                    ):
                        old_transcript_dir.rmdir()
                except OSError:
                    pass

                logger.info(
                    "Renamed output directory: %s -> %s",
                    old_transcript_dir.name,
                    new_transcript_dir.name,
                )
            except Exception as e:
                logger.error(f"Error renaming output directory: {e}")
                # Rollback transaction
                transaction.rollback()
                return False

        # Rename files inside directory that contain old name
        if new_transcript_dir.exists():
            rename_files_in_directory(
                old_transcript_dir, new_transcript_dir, old_name, new_name
            )

        # Invalidate path resolution cache for renamed files
        # With UUID-based keys, we mainly need to clear path-to-UUID lookups
        invalidate_path_cache(str(transcript_path))
        invalidate_path_cache(str(new_transcript_path))
        # Note: With UUID-based keys, the cache is less critical since UUIDs don't change
        # But we still cache path lookups for performance

        if not dry_run:
            logger.info("Successfully renamed all files: %s -> %s", old_name, new_name)

        return True

    except Exception as e:
        log_error("FILE_RENAME", f"Error renaming transcript files: {e}", exception=e)
        logger.error("Error renaming files: %s", e)
        return False


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
