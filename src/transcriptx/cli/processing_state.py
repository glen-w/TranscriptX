"""
Processing state management for batch workflows.

This module provides centralized state management for tracking processed files,
including loading, saving, validation, and migration utilities.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import get_logger, log_error
from transcriptx.core.utils.paths import DATA_DIR
from transcriptx.core.utils.path_utils import resolve_file_path

# Database integration
try:
    from transcriptx.database import init_database, get_session, FileTrackingService
    from transcriptx.database.repositories import TranscriptFileRepository

    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False
    init_database = None
    get_session = None
    TranscriptFileRepository = None
    FileTrackingService = None

logger = get_logger()

# Processing state file location
PROCESSING_STATE_FILE = Path(DATA_DIR) / "processing_state.json"

# UUID cache to avoid repeated database queries
_uuid_cache: Dict[str, str] = {}


def _is_uuid_format(key: str) -> bool:
    """
    Check if a key looks like a UUID (36 chars, contains hyphens).

    Args:
        key: Key to check

    Returns:
        True if key looks like a UUID
    """
    uuid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
    )
    return bool(uuid_pattern.match(key))


def _ensure_transcript_uuid(transcript_path: Optional[str]) -> str:
    """
    Get or create TranscriptFile in database and return its UUID.

    If database is disabled, generates a UUID with a warning.
    Caches UUID lookups to avoid repeated database queries.

    Args:
        transcript_path: Path to transcript file (optional)

    Returns:
        UUID string for the transcript file
    """
    # Check cache first
    if transcript_path and transcript_path in _uuid_cache:
        return _uuid_cache[transcript_path]

    # If database is available and enabled
    if DATABASE_AVAILABLE and get_session and TranscriptFileRepository:
        try:
            config = get_config()
            if hasattr(config, "database") and config.database.enabled:
                # Initialize database if needed
                init_database()

                # Get or create TranscriptFile
                session = get_session()
                try:
                    file_repo = TranscriptFileRepository(session)

                    if transcript_path:
                        # Try to find existing file
                        existing = file_repo.get_transcript_file_by_path(
                            transcript_path
                        )
                        if existing:
                            uuid = existing.uuid
                            # Cache it
                            _uuid_cache[transcript_path] = uuid
                            return uuid

                        # Create new file record
                        transcript_file = file_repo.create_or_get_transcript_file(
                            file_path=transcript_path,
                            file_name=Path(transcript_path).name,
                        )
                        uuid = transcript_file.uuid
                        # Cache it
                        _uuid_cache[transcript_path] = uuid
                        return uuid
                    else:
                        # No transcript path yet, generate UUID
                        # This will be synced when transcript is created
                        uuid = str(uuid4())
                        logger.debug(
                            f"Generated UUID for transcript (no path yet): {uuid}"
                        )
                        return uuid
                finally:
                    session.close()
        except Exception as e:
            logger.warning(
                f"Failed to get UUID from database, generating fallback UUID: {e}"
            )
            # Fall through to UUID generation

    # Database disabled or error - generate UUID with warning
    uuid = str(uuid4())
    if transcript_path:
        logger.warning(
            f"Database not available or disabled. Generated UUID for {transcript_path}. "
            "This UUID may not sync with database later."
        )
        _uuid_cache[transcript_path] = uuid
    else:
        logger.debug("Generated UUID without database (no transcript path)")

    return uuid


def load_processing_state(
    state_file: str | Path | None = None,
    validate: bool = True,
    *,
    skip_migration: bool = False,
) -> Dict[str, Any]:
    """
    Load processing state from JSON file with optional validation and locking.

    Args:
        validate: If True, validate state after loading

    Returns:
        Dictionary with processing state
    """
    from transcriptx.core.utils.file_lock import FileLock, cleanup_stale_locks

    try:
        # Clean up stale locks
        target_file = Path(state_file) if state_file else PROCESSING_STATE_FILE
        cleanup_stale_locks(target_file.with_suffix(".lock"))

        if target_file.exists():
            with FileLock(target_file, timeout=5, blocking=False) as lock:
                if not lock.acquired:
                    logger.warning("State file is locked, using cached or empty state")
                    # Return empty state if locked (read-only access)
                    return {"processed_files": {}}

                with open(target_file, "r") as f:
                    state = json.load(f)

                # Auto-validate if requested
                if validate:
                    from transcriptx.core.utils.state_utils import (
                        validate_processing_state,
                    )

                    validation_result = validate_processing_state(target_file)

                    if not validation_result["valid"]:
                        logger.warning(
                            f"State file validation found issues: {validation_result['errors']}"
                        )

                        # Auto-repair if possible
                        if validation_result["errors"]:
                            from transcriptx.core.utils.state_utils import (
                                repair_processing_state,
                            )

                            repair_result = repair_processing_state(
                                backup=True, dry_run=False
                            )
                            if repair_result["repaired"]:
                                logger.info(
                                    f"Auto-repaired state file: {repair_result['entries_repaired']} entries"
                                )
                                # Reload after repair
                                with open(target_file, "r") as f:
                                    state = json.load(f)

                if not skip_migration and validate:
                    # Check if migration is needed (old format uses path-based keys)
                    processed_files = state.get("processed_files", {})
                    if processed_files:
                        # Check if any key is not a UUID (old format)
                        all_keys = list(processed_files.keys())
                        needs_migration = not all(_is_uuid_format(key) for key in all_keys)

                        if needs_migration:
                            logger.info(
                                "Detected old format (path-based keys), migrating to UUID-based keys..."
                            )
                            try:
                                migration_result = migrate_processing_state_to_uuid_keys()
                                if migration_result.get("migrated"):
                                    logger.info(
                                        f"✅ Migration complete: {migration_result['entries_migrated']} entries migrated"
                                    )
                                    # Reload state after migration
                                    with open(target_file, "r") as f:
                                        state = json.load(f)
                                else:
                                    logger.debug(
                                        f"Migration skipped: {migration_result.get('reason', 'unknown')}"
                                    )
                            except Exception as e:
                                logger.warning(
                                    f"Migration failed, continuing with existing format: {e}"
                                )

                return state
    except json.JSONDecodeError as e:
        logger.error(f"State file is corrupted (invalid JSON): {e}")
        if not validate:
            return {"processed_files": {}}
        # Try to restore from backup
        from transcriptx.core.utils.state_backup import (
            list_backups,
            restore_from_backup,
        )

        backups = list_backups()
        if backups:
            logger.info("Attempting to restore from backup...")
            if restore_from_backup(Path(backups[0]["path"])):
                logger.info("State restored from backup")
                return load_processing_state(state_file=state_file, validate=False)
        return {"processed_files": {}}
    except Exception as e:
        log_error(
            "PROCESSING_STATE", f"Error loading processing state: {e}", exception=e
        )

    return {"processed_files": {}}


def save_processing_state(state: Dict[str, Any], state_file: str | Path | None = None) -> None:
    """
    Save processing state to JSON file with atomic write, automatic backup, and locking.

    Uses atomic write pattern: write to temporary file, then atomic rename.
    Creates backup before writing to prevent data loss.
    Uses file locking to prevent concurrent access.

    Args:
        state: Processing state dictionary
    """
    from transcriptx.core.utils.state_backup import create_backup
    from transcriptx.core.utils.file_lock import FileLock

    try:
        target_file = Path(state_file) if state_file else PROCESSING_STATE_FILE
        target_file.parent.mkdir(parents=True, exist_ok=True)

        # Acquire lock before writing
        with FileLock(target_file, timeout=30) as lock:
            if not lock.acquired:
                raise RuntimeError("Could not acquire lock for state file")

            # Create backup before updating (if file exists)
            if target_file.exists():
                create_backup(target_file)

            # Write to temporary file first
            temp_file = target_file.with_suffix(".tmp")
            try:
                with open(temp_file, "w") as f:
                    json.dump(state, f, indent=2)

                # Atomic rename (this is atomic on most filesystems)
                temp_file.replace(target_file)
            except Exception as e:
                # Clean up temp file on error
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                    except Exception:
                        pass
                raise
    except Exception as e:
        log_error(
            "PROCESSING_STATE", f"Error saving processing state: {e}", exception=e
        )


def is_file_processed(file_path: Path, state: Optional[Dict[str, Any]] = None) -> bool:
    """
    Check if a file has already been processed.

    Uses database first, falls back to JSON state file for backward compatibility.

    Args:
        file_path: Path to WAV file
        state: Optional processing state (if None, will load from JSON as fallback)

    Returns:
        True if file has been processed, False otherwise
    """
    # Try database first
    if DATABASE_AVAILABLE and get_session and FileTrackingService:
        try:
            from transcriptx.cli.audio_fingerprinting import (
                compute_audio_fingerprint,
                compute_fingerprint_hash,
            )

            session = get_session()
            tracking_service = FileTrackingService(session)

            # Compute fingerprint to find entity
            fingerprint = compute_audio_fingerprint(file_path)
            if fingerprint is not None:
                fingerprint_hash = compute_fingerprint_hash(fingerprint)
                entity = tracking_service.find_file_by_fingerprint(fingerprint_hash)

                if entity:
                    # Check if there are completed processing events
                    events = tracking_service.event_repo.get_events_by_entity(
                        entity.id, event_type="transcription", limit=1
                    )
                    if events and events[0].event_status == "completed":
                        return True
        except Exception as e:
            logger.debug(f"Database check failed, falling back to JSON: {e}")

    # Fallback to JSON state file
    if state is None:
        state = load_processing_state()

    file_key = str(file_path.resolve())
    processed_files = state.get("processed_files", {})

    # Search for entry by audio_path (works with both UUID and path keys)
    for key, entry in processed_files.items():
        entry_audio_path = entry.get("audio_path", "")
        # Check if audio_path matches (for UUID-based keys)
        if entry_audio_path == file_key:
            # Check if processing was completed successfully
            return entry.get("status") in ("completed", "processed")
        # Also check if key itself is the path (backward compatibility with old format)
        if key == file_key:
            return entry.get("status") in ("completed", "processed")

    # Also check by filename (for portability)
    filename = file_path.name
    for key, entry in processed_files.items():
        entry_audio_path = entry.get("audio_path", "")
        if entry_audio_path and Path(entry_audio_path).name == filename:
            if entry.get("status") in ("completed", "processed"):
                return True
        # Backward compatibility: check if key is a path with matching filename
        if not _is_uuid_format(key) and Path(key).name == filename:
            if entry.get("status") in ("completed", "processed"):
                return True

    return False


def mark_file_processed(file_path: Path, metadata: Dict[str, Any]) -> None:
    """
    Mark a file as processed.

    PRIMARY: Uses database (FileTrackingService) for tracking.
    FALLBACK: Also writes to JSON state file for backward compatibility.

    Args:
        file_path: Path to processed file
        metadata: Processing metadata (mp3_path, transcript_path, type, tags, etc.)
    """
    # Database tracking is now handled in file_processor.py during processing
    # This function is kept for backward compatibility and as a fallback

    # Still write to JSON for backward compatibility (can be removed later)
    from transcriptx.core.utils.state_schema import enrich_state_entry

    state = load_processing_state()

    if "processed_files" not in state:
        state["processed_files"] = {}

    # Get or create UUID for transcript
    transcript_path = metadata.get("transcript_path")
    transcript_uuid = _ensure_transcript_uuid(transcript_path)

    # Create base entry
    status = metadata.get("status", "completed")
    entry = {
        "transcript_uuid": transcript_uuid,
        "audio_path": str(file_path.resolve()),  # Keep as metadata
        "processed_at": datetime.now().isoformat(),
        "status": status,
        **metadata,
    }

    # Ensure mp3_path and transcript_path are always set (even if None for failed entries)
    # This ensures state validation passes for failed transcriptions
    if "mp3_path" not in entry:
        entry["mp3_path"] = metadata.get("mp3_path")  # May be None
    if "transcript_path" not in entry:
        entry["transcript_path"] = metadata.get("transcript_path")  # May be None

    # For failed/error entries, explicitly set None if paths are missing
    if status in ["failed", "error"]:
        if entry.get("mp3_path") is None and "mp3_path" not in metadata:
            entry["mp3_path"] = None
        if entry.get("transcript_path") is None and "transcript_path" not in metadata:
            entry["transcript_path"] = None

    # Enrich with computed fields if transcript_path is available
    if transcript_path:
        entry = enrich_state_entry(entry, transcript_path)

    # Use UUID as primary key, but also preserve legacy path key
    state["processed_files"][transcript_uuid] = entry
    path_key = str(file_path.resolve())
    if path_key not in state["processed_files"]:
        state["processed_files"][path_key] = entry

    # Save to JSON (backward compatibility - can be removed in future)
    save_processing_state(state)


def migrate_processing_state_to_uuid_keys() -> Dict[str, Any]:
    """
    Migrate processing_state.json from path-based keys to UUID-based keys.

    This function:
    1. Detects if state uses old format (path-based keys)
    2. For each path-keyed entry:
       - Tries to find matching TranscriptFile in database by file_path
       - If found: uses its UUID
       - If not found: generates UUID, optionally creates DB record
    3. Creates new entry with UUID key
    4. Preserves all metadata
    5. Creates backup before migration

    Returns:
        Migration result dictionary with stats
    """
    from transcriptx.core.utils.state_backup import create_backup

    state = load_processing_state(validate=False, skip_migration=True)
    processed_files = state.get("processed_files", {})

    if not processed_files:
        return {
            "migrated": False,
            "reason": "No entries to migrate",
            "entries_migrated": 0,
        }

    # Check if already migrated (all keys are UUIDs)
    all_keys = list(processed_files.keys())
    if all(_is_uuid_format(key) for key in all_keys):
        return {
            "migrated": False,
            "reason": "Already using UUID-based keys",
            "entries_migrated": 0,
        }

    # Create backup before migration
    logger.info("Creating backup before migration...")
    create_backup(PROCESSING_STATE_FILE)

    # Migrate entries
    migrated_entries = {}
    entries_migrated = 0
    entries_with_db_uuid = 0
    entries_with_generated_uuid = 0

    for old_key, entry in processed_files.items():
        # Skip if already UUID format
        if _is_uuid_format(old_key):
            migrated_entries[old_key] = entry
            continue

        # Extract transcript_path from entry
        transcript_path = entry.get("transcript_path")
        if not transcript_path:
            # No transcript path, generate UUID
            uuid = _ensure_transcript_uuid(None)
            entry["transcript_uuid"] = uuid
            migrated_entries[uuid] = entry
            entries_migrated += 1
            entries_with_generated_uuid += 1
            continue

        # Try to get UUID from database or generate one
        uuid = _ensure_transcript_uuid(transcript_path)

        # Check if we got UUID from database (by checking if it's in cache with path)
        if transcript_path in _uuid_cache:
            # This means we found it in DB or created it
            # Check if it was from DB by trying to look it up
            if DATABASE_AVAILABLE and get_session and TranscriptFileRepository:
                try:
                    config = get_config()
                    if hasattr(config, "database") and config.database.enabled:
                        init_database()
                        session = get_session()
                        try:
                            file_repo = TranscriptFileRepository(session)
                            existing = file_repo.get_transcript_file_by_path(
                                transcript_path
                            )
                            if existing:
                                entries_with_db_uuid += 1
                        finally:
                            session.close()
                except Exception:
                    pass

        # Add UUID to entry
        entry["transcript_uuid"] = uuid
        # Also preserve audio_path if it was the old key
        if "audio_path" not in entry:
            entry["audio_path"] = old_key

        # Use UUID as new key
        migrated_entries[uuid] = entry
        entries_migrated += 1

        if entries_with_db_uuid + entries_with_generated_uuid < entries_migrated:
            entries_with_generated_uuid += 1

    # Update state with migrated entries
    state["processed_files"] = migrated_entries

    # Save migrated state
    save_processing_state(state)

    logger.info(
        f"✅ Migrated {entries_migrated} entries to UUID-based keys "
        f"({entries_with_db_uuid} from database, {entries_with_generated_uuid} generated)"
    )

    return {
        "migrated": True,
        "entries_migrated": entries_migrated,
        "entries_with_db_uuid": entries_with_db_uuid,
        "entries_with_generated_uuid": entries_with_generated_uuid,
    }


def get_current_transcript_path_from_state(transcript_path: str) -> Optional[str]:
    """
    Get the current transcript path from processing state.

    DEPRECATED: Use resolve_file_path() instead.
    This function is kept for backward compatibility.

    Args:
        transcript_path: Original transcript path (may be old path if file was renamed)

    Returns:
        Current transcript path from processing state if found, None otherwise
    """
    try:
        # Backward compatibility: scan state entries for current_transcript_path
        state = load_processing_state(validate=False)
        processed_files = state.get("processed_files", {})
        for entry in processed_files.values():
            if not isinstance(entry, dict):
                continue
            if entry.get("transcript_path") == transcript_path:
                return entry.get("current_transcript_path") or entry.get("transcript_path")
            if entry.get("current_transcript_path") == transcript_path:
                return entry.get("current_transcript_path")

        # Use unified resolution function
        resolved = resolve_file_path(
            transcript_path, file_type="transcript", validate_state=True
        )
        return resolved
    except FileNotFoundError:
        return None
