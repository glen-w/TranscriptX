"""
Processing state validation and repair utilities.

This module provides functions to validate and repair the processing_state.json file,
ensuring consistency with the file system and fixing common issues.
"""

import json
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import DATA_DIR
from transcriptx.core.utils.state_schema import (
    validate_state_entry,
    validate_state_paths,
    migrate_state_entry,
    enrich_state_entry,
)
from transcriptx.core.utils.path_utils import (
    resolve_file_path,
)

logger = get_logger()

PROCESSING_STATE_FILE = Path(DATA_DIR) / "processing_state.json"


def load_processing_state(state_file: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load processing state from disk.

    Args:
        state_file: Path to state file (defaults to standard location)

    Returns:
        Parsed state dict or empty dict if missing/unreadable.
    """
    if state_file is None:
        state_file = PROCESSING_STATE_FILE

    if not state_file.exists():
        return {}

    try:
        with open(state_file, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading processing state: {e}")
        return {}


def validate_processing_state(state_file: Optional[Path] = None) -> Dict[str, Any]:
    """
    Validate entire processing state file.

    Args:
        state_file: Path to state file (defaults to standard location)

    Returns:
        Dictionary with validation results:
        {
            "valid": bool,
            "errors": list,
            "warnings": list,
            "entries_checked": int,
            "entries_valid": int,
            "entries_invalid": int
        }
    """
    if state_file is None:
        state_file = PROCESSING_STATE_FILE

    result = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "entries_checked": 0,
        "entries_valid": 0,
        "entries_invalid": 0,
    }

    if not state_file.exists():
        result["errors"].append(f"State file does not exist: {state_file}")
        result["valid"] = False
        return result

    try:
        with open(state_file, "r") as f:
            state = json.load(f)
    except json.JSONDecodeError as e:
        result["errors"].append(f"State file is not valid JSON: {e}")
        result["valid"] = False
        return result
    except Exception as e:
        result["errors"].append(f"Error reading state file: {e}")
        result["valid"] = False
        return result

    processed_files = state.get("processed_files", {})
    result["entries_checked"] = len(processed_files)

    for file_key, entry in processed_files.items():
        # Validate entry schema
        is_valid, schema_errors = validate_state_entry(entry)
        if not is_valid:
            result["errors"].extend([f"{file_key}: {err}" for err in schema_errors])
            result["entries_invalid"] += 1
            result["valid"] = False
            continue

        # Validate paths exist
        is_valid, path_errors = validate_state_paths(entry)
        if not is_valid:
            result["warnings"].extend([f"{file_key}: {err}" for err in path_errors])
            # Path errors are warnings, not critical errors

        # Validate analysis fields if present
        if "analysis_status" in entry or "analysis_modules_requested" in entry:
            analysis_warnings = []

            # Check analysis_completed flag consistency
            analysis_completed = entry.get("analysis_completed", False)
            analysis_status = entry.get("analysis_status", "not_started")
            modules_run = entry.get("analysis_modules_run", [])

            if analysis_completed and not modules_run:
                analysis_warnings.append(
                    "analysis_completed is True but no modules_run"
                )

            if analysis_completed and analysis_status != "completed":
                analysis_warnings.append(
                    f"analysis_completed is True but analysis_status is '{analysis_status}'"
                )

            # Check modules_run is subset of modules_requested
            modules_requested = entry.get("analysis_modules_requested", [])
            if modules_run and modules_requested:
                if not all(m in modules_requested for m in modules_run):
                    analysis_warnings.append(
                        "analysis_modules_run contains modules not in analysis_modules_requested"
                    )

            # Check timestamp format
            if "analysis_timestamp" in entry and entry["analysis_timestamp"]:
                try:
                    from datetime import datetime

                    datetime.fromisoformat(entry["analysis_timestamp"])
                except (ValueError, TypeError):
                    analysis_warnings.append(
                        f"Invalid analysis_timestamp format: {entry['analysis_timestamp']}"
                    )

            if analysis_warnings:
                result["warnings"].extend(
                    [f"{file_key}: {warn}" for warn in analysis_warnings]
                )

        result["entries_valid"] += 1

    return result


def repair_processing_state(
    state_file: Optional[Path] = None, backup: bool = True, dry_run: bool = False
) -> Dict[str, Any]:
    """
    Repair processing state file.

    This function:
    - Migrates entries to current schema
    - Fixes missing paths using file system search
    - Removes invalid entries (with backup)
    - Updates stale paths
    - Enriches entries with computed fields

    Args:
        state_file: Path to state file (defaults to standard location)
        backup: Create backup before repair
        dry_run: Show what would be repaired without making changes

    Returns:
        Dictionary with repair results:
        {
            "repaired": bool,
            "entries_repaired": int,
            "entries_removed": int,
            "backup_path": str or None,
            "changes": list
        }
    """
    if state_file is None:
        state_file = PROCESSING_STATE_FILE

    result = {
        "repaired": False,
        "entries_repaired": 0,
        "entries_removed": 0,
        "backup_path": None,
        "changes": [],
    }

    if not state_file.exists():
        logger.warning(f"State file does not exist: {state_file}")
        return result

    # Create backup
    if backup and not dry_run:
        backup_path = state_file.with_suffix(".json.backup")
        try:
            shutil.copy2(state_file, backup_path)
            result["backup_path"] = str(backup_path)
            logger.info(f"Created backup: {backup_path}")
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            if not dry_run:
                return result

    try:
        with open(state_file, "r") as f:
            state = json.load(f)
    except Exception as e:
        logger.error(f"Error reading state file: {e}")
        return result

    processed_files = state.get("processed_files", {})
    entries_to_remove = []

    for file_key, entry in processed_files.items():
        changes = []

        # Migrate to current schema
        migrated = migrate_state_entry(entry)
        if migrated != entry:
            changes.append("Migrated to current schema")
            entry = migrated

        # Try to fix missing paths
        transcript_path = entry.get("transcript_path")
        if transcript_path:
            # Enrich entry with computed fields
            enriched = enrich_state_entry(entry, transcript_path)
            if enriched != entry:
                changes.append("Enriched with computed fields")
                entry = enriched

            # Try to resolve missing paths
            if not Path(entry.get("transcript_path", "")).exists():
                try:
                    resolved = resolve_file_path(
                        transcript_path, file_type="transcript", validate_state=False
                    )
                    entry["transcript_path"] = resolved
                    changes.append(f"Fixed transcript_path: {resolved}")
                except FileNotFoundError:
                    pass

            # Fix mp3_path if missing, None, or pointing to non-existent file
            # This is especially important for completed entries which require mp3_path
            mp3_path = entry.get("mp3_path")
            status = entry.get("status", "")

            # Check if mp3_path needs fixing
            mp3_missing_or_none = not mp3_path or mp3_path is None
            mp3_file_missing = mp3_path and not Path(mp3_path).exists()
            needs_mp3_fix = mp3_missing_or_none or mp3_file_missing

            # Try to resolve mp3_path if it's missing or invalid
            # mp3_path is optional (analysis can complete without audio), but we try to resolve it if missing
            if needs_mp3_fix:
                try:
                    resolved = resolve_file_path(
                        transcript_path, file_type="audio", validate_state=False
                    )
                    entry["mp3_path"] = resolved
                    if mp3_missing_or_none:
                        changes.append(f"Fixed missing mp3_path: {resolved}")
                    else:
                        changes.append(f"Fixed mp3_path: {mp3_path} -> {resolved}")
                except FileNotFoundError:
                    # If we can't resolve mp3_path, set it to None (it's optional for analysis)
                    # This prevents validation errors while keeping the entry valid
                    if mp3_path is not None:
                        entry["mp3_path"] = None
                        changes.append("Set mp3_path to None (audio file not found)")
                    elif "mp3_path" not in entry:
                        entry["mp3_path"] = None
                        changes.append(
                            "Set missing mp3_path to None (audio file not found)"
                        )
                    # Log as info since this is expected for some transcripts
                    logger.debug(
                        f"Could not resolve mp3_path for entry {file_key}, set to None"
                    )

        # Fix inconsistent analysis state
        if "analysis_status" in entry or "analysis_modules_requested" in entry:
            analysis_changes = []

            # Recalculate analysis_status from modules_run
            modules_requested = entry.get("analysis_modules_requested", [])
            modules_run = entry.get("analysis_modules_run", [])
            errors = entry.get("analysis_errors", [])

            if not modules_requested:
                calculated_status = "not_started"
            elif errors and not modules_run:
                calculated_status = "failed"
            elif set(modules_run) == set(modules_requested):
                calculated_status = "completed"
            elif modules_run:
                calculated_status = "partial"
            else:
                calculated_status = "failed"

            current_status = entry.get("analysis_status")
            if current_status != calculated_status:
                entry["analysis_status"] = calculated_status
                analysis_changes.append(
                    f"Fixed analysis_status: {current_status} -> {calculated_status}"
                )

            # Update analysis_completed flag based on actual state
            analysis_completed = calculated_status == "completed"
            if entry.get("analysis_completed") != analysis_completed:
                entry["analysis_completed"] = analysis_completed
                analysis_changes.append(
                    f"Fixed analysis_completed: {entry.get('analysis_completed')} -> {analysis_completed}"
                )

            # Fix modules_failed if inconsistent
            modules_failed = entry.get("analysis_modules_failed", [])
            expected_failed = [m for m in modules_requested if m not in modules_run]
            if set(modules_failed) != set(expected_failed):
                entry["analysis_modules_failed"] = expected_failed
                analysis_changes.append("Fixed analysis_modules_failed")

            if analysis_changes:
                changes.extend(analysis_changes)

        # Check if entry is still valid
        is_valid, errors = validate_state_entry(entry)
        if not is_valid:
            # Entry is invalid, mark for removal
            entries_to_remove.append(file_key)
            result["changes"].append(
                f"{file_key}: Marked for removal (invalid: {errors})"
            )
        elif changes:
            # Entry was repaired
            processed_files[file_key] = entry
            result["entries_repaired"] += 1
            result["changes"].append(f"{file_key}: {', '.join(changes)}")

    # Remove invalid entries
    for file_key in entries_to_remove:
        processed_files.pop(file_key, None)
        result["entries_removed"] += 1

    if not dry_run and (
        result["entries_repaired"] > 0 or result["entries_removed"] > 0
    ):
        # Save repaired state
        state["processed_files"] = processed_files
        try:
            with open(state_file, "w") as f:
                json.dump(state, f, indent=2)
            result["repaired"] = True
            logger.info(
                f"Repaired state file: {result['entries_repaired']} entries repaired, {result['entries_removed']} entries removed"
            )
        except Exception as e:
            logger.error(f"Error saving repaired state: {e}")
            result["repaired"] = False

    return result


def get_analysis_history(transcript_path: str) -> Dict[str, Any]:
    """
    Get analysis history from processing state.

    Args:
        transcript_path: Path to transcript file

    Returns:
        Dictionary with analysis history, or None if not found
    """
    try:
        state = load_processing_state()
        if not state:
            return None

        processed_files = state.get("processed_files", {})

        # Find entry matching this transcript
        for file_key, entry in processed_files.items():
            if entry.get("transcript_path") == transcript_path:
                from transcriptx.core.utils.state_schema import get_analysis_status

                return get_analysis_status(entry)

        return None
    except Exception as e:
        logger.error(f"Error getting analysis history: {e}")
        return None


def has_analysis_completed(transcript_path: str, modules: List[str]) -> bool:
    """
    Check if requested modules have completed successfully.

    Args:
        transcript_path: Path to transcript file
        modules: List of module names to check

    Returns:
        True if all requested modules have completed successfully, False otherwise
    """
    try:
        history = get_analysis_history(transcript_path)
        if not history:
            return False

        modules_run = set(history.get("modules_run", []))
        modules_requested = set(history.get("modules_requested", []))
        requested_modules = set(modules)

        if not requested_modules:
            return False

        # All requested modules must be in modules_run if tracked
        if requested_modules.issubset(modules_run):
            return True

        # Fallback: completed status with requested coverage
        if (
            history.get("completed") or history.get("status") == "completed"
        ) and requested_modules.issubset(modules_requested):
            return True

        return False
    except Exception as e:
        logger.error(f"Error checking analysis completion: {e}")
        return False


def get_missing_modules(
    transcript_path: str, requested_modules: List[str]
) -> List[str]:
    """
    Get list of modules that haven't been run or failed.

    Args:
        transcript_path: Path to transcript file
        requested_modules: List of module names to check

    Returns:
        List of modules that are missing (not run or failed)
    """
    try:
        history = get_analysis_history(transcript_path)
        if not history:
            # No analysis history, all modules are missing
            return requested_modules

        modules_run = set(history.get("modules_run", []))
        modules_failed = set(history.get("modules_failed", []))
        requested_set = set(requested_modules)

        # Missing modules are those requested but not run and not explicitly failed
        # (failed modules might be retryable)
        missing = requested_set - modules_run

        return list(missing)
    except Exception as e:
        logger.error(f"Error getting missing modules: {e}")
        return requested_modules


def get_transcript_analysis_status(transcript_path: str) -> Optional[Dict[str, Any]]:
    """
    Get analysis status for a specific transcript.

    Args:
        transcript_path: Path to transcript file

    Returns:
        Dictionary with analysis status, or None if not found
    """
    return get_analysis_history(transcript_path)


def list_transcripts_with_analysis() -> List[Dict[str, Any]]:
    """
    List all transcripts that have analysis history.

    Returns:
        List of dictionaries with transcript_path and analysis_status
    """
    try:
        if not PROCESSING_STATE_FILE.exists():
            return []

        with open(PROCESSING_STATE_FILE, "r") as f:
            state = json.load(f)

        processed_files = state.get("processed_files", {})
        transcripts_with_analysis = []

        for file_key, entry in processed_files.items():
            if (
                entry.get("analysis_status")
                and entry.get("analysis_status") != "not_started"
            ):
                from transcriptx.core.utils.state_schema import get_analysis_status

                status = get_analysis_status(entry)
                transcripts_with_analysis.append(
                    {
                        "transcript_path": entry.get("transcript_path"),
                        "analysis_status": status,
                    }
                )

        return transcripts_with_analysis
    except Exception as e:
        logger.error(f"Error listing transcripts with analysis: {e}")
        return []


def list_transcripts_needing_analysis(modules: Optional[List[str]] = None) -> List[str]:
    """
    List transcripts that need analysis (not started, partial, or failed).

    Args:
        modules: Optional list of specific modules to check for

    Returns:
        List of transcript paths that need analysis
    """
    try:
        if not PROCESSING_STATE_FILE.exists():
            return []

        with open(PROCESSING_STATE_FILE, "r") as f:
            state = json.load(f)

        processed_files = state.get("processed_files", {})
        needing_analysis = []

        for file_key, entry in processed_files.items():
            transcript_path = entry.get("transcript_path")
            if not transcript_path:
                continue

            analysis_status = entry.get("analysis_status", "not_started")

            # Check if needs analysis
            needs_analysis = False
            if analysis_status == "not_started":
                needs_analysis = True
            elif analysis_status in ["partial", "failed"]:
                if modules:
                    # Check if specific modules are missing
                    missing = get_missing_modules(transcript_path, modules)
                    needs_analysis = len(missing) > 0
                else:
                    needs_analysis = True
            elif analysis_status == "completed" and modules:
                # Check if all requested modules completed
                if not has_analysis_completed(transcript_path, modules):
                    needs_analysis = True

            if needs_analysis:
                needing_analysis.append(transcript_path)

        return needing_analysis
    except Exception as e:
        logger.error(f"Error listing transcripts needing analysis: {e}")
        return []
