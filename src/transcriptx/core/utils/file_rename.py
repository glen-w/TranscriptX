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

import questionary
from rich.console import Console

from transcriptx.core.utils.logger import get_logger, log_error
from transcriptx.core.utils.paths import DATA_DIR, OUTPUTS_DIR
from transcriptx.core.utils.path_utils import (
    get_base_name,
    get_canonical_base_name,
    get_transcript_dir,
    invalidate_path_cache,
    resolve_file_path,
)
from transcriptx.core.utils.rename_transaction import RenameTransaction
from transcriptx.database import get_session, FileTrackingService
from uuid import uuid4

console = Console()
logger = get_logger()

# Processing state file location
PROCESSING_STATE_FILE = Path(DATA_DIR) / "processing_state.json"


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
                    Path(DATA_DIR) / "recordings",
                    Path(OUTPUTS_DIR) / "recordings",
                ]
                exts = [".wav", ".mp3", ".m4a", ".flac", ".aac", ".ogg"]
                for base in (canonical_base, transcript_base, base_without_suffix):
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
            Path(DATA_DIR) / "recordings",
            Path(OUTPUTS_DIR) / "recordings",
        ]
        for base in (transcript_base, base_without_suffix):
            for recordings_dir in recordings_dirs:
                if not recordings_dir.exists():
                    continue
                for ext in audio_extensions:
                    audio_file = recordings_dir / f"{base}{ext}"
                    if audio_file.exists():
                        return audio_file

        # If still not found, use transcript file modification time as fallback
        transcript_file = Path(transcript_path)
        if transcript_file.exists():
            logger.info(
                "Using transcript file modification time as fallback for date extraction"
            )
            return transcript_file

    except Exception as e:
        log_error("FILE_RENAME", f"Error finding original audio file: {e}", exception=e)

    return None


def _update_database_paths(old_path: str, new_path: str) -> None:
    """
    Update database records when transcript files are renamed.

    Uses UUID from processing state to find and update TranscriptFile record.

    Args:
        old_path: Old transcript path
        new_path: New transcript path
    """
    try:
        # Try to import database functions
        from transcriptx.database import init_database, get_session
        from transcriptx.database.repositories import TranscriptFileRepository
        from transcriptx.database.transcript_manager import TranscriptManager

        init_database()

        # Get UUID from processing state
        transcript_uuid = None
        if PROCESSING_STATE_FILE.exists():
            with open(PROCESSING_STATE_FILE, "r") as f:
                state = json.load(f)
            processed_files = state.get("processed_files", {})
            # Find entry with matching old_path
            for key, metadata in processed_files.items():
                if metadata.get("transcript_path") == old_path:
                    transcript_uuid = metadata.get("transcript_uuid")
                    break

        # Update TranscriptFile by UUID if we have it
        if transcript_uuid:
            session = get_session()
            try:
                file_repo = TranscriptFileRepository(session)
                updated = file_repo.update_transcript_file_path(
                    file_uuid=transcript_uuid, new_file_path=new_path
                )
                if updated:
                    logger.info(
                        f"Updated database TranscriptFile path by UUID: {transcript_uuid}"
                    )
            finally:
                session.close()

        # Also update conversation records (for backward compatibility)
        manager = TranscriptManager()
        conversation = manager.get_conversation_by_transcript_path(old_path)
        if conversation:
            # Update transcript_file_path if it matches old path
            if conversation.transcript_file_path == old_path:
                conversation.transcript_file_path = new_path
            # Update readable_transcript_path if it matches old path
            if conversation.readable_transcript_path == old_path:
                conversation.readable_transcript_path = new_path

            # Commit changes
            manager.conversation_repo.session.commit()
            logger.info(f"Updated database paths for conversation {conversation.id}")
    except ImportError:
        # Database not available, skip update
        pass
    except Exception as e:
        # Don't fail rename if database update fails
        log_error("FILE_RENAME", f"Error updating database paths: {e}", exception=e)


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

        with open(PROCESSING_STATE_FILE, "r") as f:
            state = json.load(f)

        processed_files = state.get("processed_files", {})
        updated = False

        # Pre-compute canonical bases
        old_canonical_base = get_canonical_base_name(old_path)
        new_canonical_base = get_canonical_base_name(new_path)
        new_output_dir = Path(OUTPUTS_DIR) / new_canonical_base

        # Find entry by searching for old transcript_path (works with both UUID and path keys)
        for key, metadata in processed_files.items():
            if metadata.get("transcript_path") != old_path:
                continue

            # Update transcript path
            metadata["transcript_path"] = new_path

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
                    if step_tp == old_path:
                        transcribe_step["transcript_path"] = new_path
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
                        convert_step["mp3_path"] = metadata.get(
                            "mp3_path", old_mp3_path
                        )
                    elif step_mp3:
                        step_mp3_base = get_canonical_base_name(step_mp3)
                        if step_mp3_base == old_canonical_base:
                            step_mp3_dir = Path(step_mp3).parent
                            step_mp3_ext = Path(step_mp3).suffix
                            convert_step["mp3_path"] = str(
                                step_mp3_dir / f"{new_name}{step_mp3_ext}"
                            )

            # --- step-level paths (current top-level structure) ---
            # transcribe step
            transcribe_step = metadata.get("transcribe")
            if isinstance(transcribe_step, dict):
                step_tp = transcribe_step.get("transcript_path")
                if step_tp == old_path:
                    transcribe_step["transcript_path"] = new_path
                elif step_tp:
                    step_transcript_base = get_canonical_base_name(step_tp)
                    if step_transcript_base == old_canonical_base:
                        step_transcript_dir = Path(step_tp).parent
                        transcribe_step["transcript_path"] = str(
                            step_transcript_dir / f"{new_name}.json"
                        )

            # convert step
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

            # Update last_updated timestamp
            from datetime import datetime

            metadata["last_updated"] = datetime.now().isoformat()

            # Enrich with any missing computed fields
            metadata = enrich_state_entry(metadata, new_path)

            updated = True

        if updated:
            # Validate updated paths before saving (warnings only)
            for key, metadata in processed_files.items():
                if metadata.get("transcript_path") == new_path:
                    is_valid, errors = validate_state_paths(metadata)
                    if not is_valid:
                        logger.warning(
                            f"State entry has invalid paths after update: {errors}"
                        )

            # Use atomic save_processing_state instead of direct file write
            from transcriptx.cli.processing_state import save_processing_state

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

        # Get old paths
        old_transcript_dir = Path(get_transcript_dir(transcript_path))

        # Calculate new paths
        new_transcript_path = transcript_file.parent / f"{new_name}.json"
        new_transcript_dir = Path(OUTPUTS_DIR) / new_name

        # Check if new paths would conflict
        if new_transcript_path.exists() and new_transcript_path != transcript_file:
            console.print(
                f"[red]❌ Error: File already exists: {new_transcript_path}[/red]"
            )
            return False

        if new_transcript_dir.exists() and new_transcript_dir != old_transcript_dir:
            console.print(
                f"[red]❌ Error: Directory already exists: {new_transcript_dir}[/red]"
            )
            return False

        if dry_run:
            console.print(
                f"[cyan]DRY RUN: Would rename {old_name} -> {new_name}[/cyan]"
            )

        # Plan all rename operations in transaction
        # Rename transcript file
        if transcript_file != new_transcript_path:
            transaction.add_rename(
                transcript_file,
                new_transcript_path,
                f"Rename transcript: {old_name} -> {new_name}",
            )

        # Find and rename audio file if it exists
        # Use mp3_path from processing state to find actual audio file
        old_audio_file = None
        new_audio_file = None
        if PROCESSING_STATE_FILE.exists():
            try:
                with open(PROCESSING_STATE_FILE, "r") as f:
                    state = json.load(f)
                processed_files = state.get("processed_files", {})
                for audio_path, metadata in processed_files.items():
                    if metadata.get("transcript_path") == transcript_path:
                        mp3_path = metadata.get("mp3_path", "")
                        if mp3_path:
                            old_audio_file = Path(mp3_path)
                            if old_audio_file.exists():
                                # Calculate new MP3 path based on new name
                                mp3_dir = old_audio_file.parent
                                mp3_ext = old_audio_file.suffix
                                new_audio_file = mp3_dir / f"{new_name}{mp3_ext}"
                                break
            except Exception as e:
                logger.debug(f"Could not load processing state for MP3 rename: {e}")

        # Fallback: try to find audio file by old_name if not found in state
        if not old_audio_file or not old_audio_file.exists():
            recordings_dir = Path(DATA_DIR) / "recordings"
            audio_extensions = [".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"]
            for ext in audio_extensions:
                candidate = recordings_dir / f"{old_name}{ext}"
                if candidate.exists():
                    old_audio_file = candidate
                    new_audio_file = recordings_dir / f"{new_name}{ext}"
                    break

        # Add audio file rename to transaction if found
        if old_audio_file and old_audio_file.exists() and new_audio_file:
            if not new_audio_file.exists():
                transaction.add_rename(
                    old_audio_file,
                    new_audio_file,
                    f"Rename audio file: {old_audio_file.name} -> {new_audio_file.name}",
                )

        # Speaker map files are deprecated - no need to rename them

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

        # Add database update to transaction (if database enabled)
        transaction.add_state_update(
            _update_database_paths, str(transcript_path), str(new_transcript_path)
        )

        # Execute transaction (all file renames, state update, and database update)
        if not transaction.execute():
            console.print("[red]❌ Transaction failed, changes rolled back[/red]")
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

                console.print(
                    f"[green]✅ Renamed output directory: {old_transcript_dir.name} -> {new_transcript_dir.name}[/green]"
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

        # Note: Database update is now part of the transaction (atomic)
        # Track rename in file tracking database
        if not dry_run:
            try:
                session = get_session()
                tracking_service = FileTrackingService(session)

                # Find file entity by looking up transcript artifact
                transcript_artifact = tracking_service.artifact_repo.find_by_path(
                    str(transcript_path)
                )
                if not transcript_artifact:
                    # Try new path if old path not found
                    transcript_artifact = tracking_service.artifact_repo.find_by_path(
                        str(new_transcript_path)
                    )

                if transcript_artifact:
                    file_entity_id = transcript_artifact.file_entity_id
                    rename_group_id = str(uuid4())

                    # Collect all artifacts to rename
                    artifacts_to_rename = []

                    # Transcript artifact
                    if transcript_artifact.path == str(
                        transcript_path
                    ) or transcript_artifact.path == str(new_transcript_path):
                        artifacts_to_rename.append(
                            (
                                transcript_artifact,
                                str(transcript_path),
                                str(new_transcript_path),
                                old_name,
                                new_name,
                            )
                        )

                    # MP3 artifact (if exists)
                    if old_audio_file and new_audio_file and old_audio_file.exists():
                        mp3_artifact = tracking_service.artifact_repo.find_by_path(
                            str(old_audio_file.resolve())
                        )
                        if (
                            mp3_artifact
                            and mp3_artifact.file_entity_id == file_entity_id
                        ):
                            artifacts_to_rename.append(
                                (
                                    mp3_artifact,
                                    str(old_audio_file.resolve()),
                                    str(new_audio_file.resolve()),
                                    old_name,
                                    new_name,
                                )
                            )

                    # Rename all artifacts
                    renamed_files_list = []
                    for (
                        artifact,
                        old_path,
                        new_path,
                        old_base,
                        new_base,
                    ) in artifacts_to_rename:
                        # Update artifact path
                        tracking_service.artifact_repo.update_path(
                            artifact.id, new_path
                        )

                        # Log rename event and create rename history
                        tracking_service.log_rename(
                            file_entity_id=file_entity_id,
                            artifact_id=artifact.id,
                            old_path=old_path,
                            new_path=new_path,
                            old_name=old_base,
                            new_name=new_base,
                            rename_group_id=rename_group_id,
                            rename_reason="user_rename",
                        )

                        renamed_files_list.append({"old": old_path, "new": new_path})

                    # Update rename history with full list
                    if renamed_files_list:
                        from transcriptx.database.models import FileRenameHistory

                        rename_history_records = (
                            session.query(FileRenameHistory)
                            .filter(
                                FileRenameHistory.rename_group_id == rename_group_id
                            )
                            .all()
                        )
                        for record in rename_history_records:
                            record.renamed_files = renamed_files_list

                    session.commit()
                    logger.debug(
                        f"✅ Tracked rename: entity_id={file_entity_id}, rename_group_id={rename_group_id}"
                    )
            except Exception as tracking_error:
                logger.warning(
                    f"Rename tracking failed (non-critical): {tracking_error}"
                )
                # Continue even if tracking fails

        # Invalidate path resolution cache for renamed files
        # With UUID-based keys, we mainly need to clear path-to-UUID lookups
        invalidate_path_cache(str(transcript_path))
        invalidate_path_cache(str(new_transcript_path))
        # Note: With UUID-based keys, the cache is less critical since UUIDs don't change
        # But we still cache path lookups for performance

        if not dry_run:
            console.print(
                f"[green]✅ Successfully renamed all files: {old_name} -> {new_name}[/green]"
            )

        return True

    except Exception as e:
        log_error("FILE_RENAME", f"Error renaming transcript files: {e}", exception=e)
        console.print(f"[red]❌ Error renaming files: {e}[/red]")
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
    # Pause spinner for interactive workflow
    from transcriptx.utils.spinner import SpinnerManager

    SpinnerManager.pause_spinner()
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
    finally:
        # Resume spinner after interactive workflow
        SpinnerManager.resume_spinner()


def rename_mp3_file(mp3_path: Path, default_name: str = "") -> Optional[Path]:
    """
    Simple function to rename an MP3 file.

    Args:
        mp3_path: Path to the MP3 file to rename
        default_name: Default name to prefill (without extension)

    Returns:
        New Path if renamed, None if skipped or cancelled
    """
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
