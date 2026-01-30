"""
Processing state schema and validation utilities.

This module provides schema definitions, validation, and migration utilities
for the processing_state.json file.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple

from transcriptx.core.utils.path_utils import get_canonical_base_name
from transcriptx.core.utils.paths import OUTPUTS_DIR

# Schema version
STATE_SCHEMA_VERSION = "2.0"

# Required fields in state entries (always required)
REQUIRED_FIELDS = ["processed_at", "status"]

# Conditionally required fields (required only when status == "completed")
# Note: mp3_path is optional even for completed entries since analysis can complete without audio
CONDITIONALLY_REQUIRED_FIELDS = ["transcript_path"]

# Optional fields in state entries (new in v2.0)
OPTIONAL_FIELDS = [
    "output_dir_path",
    "analysis_completed",
    "last_updated",
    "canonical_base_name",
    "conversation_type",
    "tags",
    "type_confidence",
    "tag_details",
    "steps",
    # Analysis pipeline tracking fields
    "analysis_modules_requested",
    "analysis_modules_run",
    "analysis_modules_failed",
    "analysis_errors",
    "analysis_duration_seconds",
    "analysis_timestamp",
    "analysis_execution_order",
    "analysis_status",
]


def validate_state_entry(entry: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate state entry against schema.

    Path fields (mp3_path, transcript_path) are only required when status is "completed".
    For failed/error entries, these fields may be None or missing.

    Args:
        entry: State entry dictionary to validate

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Check always-required fields
    for field in REQUIRED_FIELDS:
        if field not in entry:
            errors.append(f"Missing required field: {field}")

    # Validate status field
    status = entry.get("status")
    if status:
        valid_statuses = ["completed", "failed", "error", "pending"]
        if status not in valid_statuses:
            errors.append(
                f"Invalid status value: {status}. Must be one of {valid_statuses}"
            )

        # Conditionally require path fields only for completed entries
        if status == "completed":
            for field in CONDITIONALLY_REQUIRED_FIELDS:
                if field not in entry or entry[field] is None:
                    errors.append(
                        f"Missing required field for completed entry: {field}"
                    )
        # For failed/error entries, paths are optional but should be set to None if missing
        elif status in ["failed", "error"]:
            # Ensure paths are set (even if None) for consistency
            for field in CONDITIONALLY_REQUIRED_FIELDS:
                if field not in entry:
                    # This is a warning, not an error - we'll fix it during migration
                    pass

    if "processed_at" in entry:
        try:
            datetime.fromisoformat(entry["processed_at"])
        except (ValueError, TypeError):
            errors.append(f"Invalid processed_at format: {entry['processed_at']}")

    # Validate analysis fields if present
    if "analysis_status" in entry:
        valid_analysis_statuses = ["completed", "partial", "failed", "not_started"]
        if entry["analysis_status"] not in valid_analysis_statuses:
            errors.append(
                f"Invalid analysis_status value: {entry['analysis_status']}. Must be one of {valid_analysis_statuses}"
            )

    if "analysis_timestamp" in entry:
        try:
            datetime.fromisoformat(entry["analysis_timestamp"])
        except (ValueError, TypeError):
            errors.append(
                f"Invalid analysis_timestamp format: {entry['analysis_timestamp']}"
            )

    if "analysis_modules_run" in entry and "analysis_modules_requested" in entry:
        modules_run = entry.get("analysis_modules_run", [])
        modules_requested = entry.get("analysis_modules_requested", [])
        if not isinstance(modules_run, list) or not isinstance(modules_requested, list):
            errors.append(
                "analysis_modules_run and analysis_modules_requested must be lists"
            )
        elif modules_run and modules_requested:
            # Check that modules_run is a subset of modules_requested
            if not all(m in modules_requested for m in modules_run):
                errors.append(
                    "analysis_modules_run must be a subset of analysis_modules_requested"
                )

    return len(errors) == 0, errors


def migrate_state_entry(
    entry: Dict[str, Any], from_version: str = "1.0"
) -> Dict[str, Any]:
    """
    Migrate state entry to current schema version.

    Args:
        entry: State entry to migrate
        from_version: Version to migrate from (default: "1.0")

    Returns:
        Migrated state entry
    """
    migrated = entry.copy()

    # Add defaults for new optional fields if missing
    if "output_dir_path" not in migrated:
        # Try to infer from transcript_path
        transcript_path = migrated.get("transcript_path", "")
        if transcript_path:
            try:
                canonical_base = get_canonical_base_name(transcript_path)
                migrated["output_dir_path"] = str(Path(OUTPUTS_DIR) / canonical_base)
            except Exception:
                migrated["output_dir_path"] = None

    if "analysis_completed" not in migrated:
        migrated["analysis_completed"] = False

    if "last_updated" not in migrated:
        # Use processed_at as fallback
        migrated["last_updated"] = migrated.get(
            "processed_at", datetime.now().isoformat()
        )

    if "canonical_base_name" not in migrated:
        transcript_path = migrated.get("transcript_path", "")
        if transcript_path:
            try:
                migrated["canonical_base_name"] = get_canonical_base_name(
                    transcript_path
                )
            except Exception:
                migrated["canonical_base_name"] = None
        else:
            migrated["canonical_base_name"] = None

    # Initialize analysis fields with defaults
    if "analysis_modules_requested" not in migrated:
        migrated["analysis_modules_requested"] = []
    if "analysis_modules_run" not in migrated:
        migrated["analysis_modules_run"] = []
    if "analysis_modules_failed" not in migrated:
        migrated["analysis_modules_failed"] = []
    if "analysis_errors" not in migrated:
        migrated["analysis_errors"] = []
    if "analysis_duration_seconds" not in migrated:
        migrated["analysis_duration_seconds"] = None
    if "analysis_timestamp" not in migrated:
        migrated["analysis_timestamp"] = None
    if "analysis_execution_order" not in migrated:
        migrated["analysis_execution_order"] = []
    if "analysis_status" not in migrated:
        # Determine status from existing data
        if migrated.get("analysis_completed", False):
            # If analysis_completed is True but no modules tracked, assume completed
            migrated["analysis_status"] = "completed"
        elif migrated.get("analysis_modules_run"):
            # If modules were run, check if all requested were completed
            modules_requested = migrated.get("analysis_modules_requested", [])
            modules_run = migrated.get("analysis_modules_run", [])
            if modules_requested and set(modules_run) == set(modules_requested):
                migrated["analysis_status"] = "completed"
            elif modules_run:
                migrated["analysis_status"] = "partial"
            else:
                migrated["analysis_status"] = "failed"
        else:
            migrated["analysis_status"] = "not_started"

    return migrated


def validate_state_paths(entry: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate that all paths in state entry exist.

    Args:
        entry: State entry to validate

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    path_fields = ["mp3_path", "transcript_path", "output_dir_path"]

    for field in path_fields:
        path = entry.get(field)
        if path:
            if not Path(path).exists():
                errors.append(f"{field} does not exist: {path}")

    return len(errors) == 0, errors


def enrich_state_entry(entry: Dict[str, Any], transcript_path: str) -> Dict[str, Any]:
    """
    Enrich state entry with computed fields.

    This function adds fields that can be computed from existing data,
    such as canonical_base_name and output_dir_path.

    Args:
        entry: State entry to enrich
        transcript_path: Path to transcript file

    Returns:
        Enriched state entry
    """
    enriched = entry.copy()

    # Add canonical base name
    try:
        enriched["canonical_base_name"] = get_canonical_base_name(transcript_path)
    except Exception:
        pass

    # Add output directory path
    try:
        canonical_base = enriched.get("canonical_base_name") or get_canonical_base_name(
            transcript_path
        )
        enriched["output_dir_path"] = str(Path(OUTPUTS_DIR) / canonical_base)
    except Exception:
        pass

    # Update last_updated timestamp
    enriched["last_updated"] = datetime.now().isoformat()

    return enriched


def update_analysis_state(
    entry: Dict[str, Any], results: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Update state entry with analysis pipeline results.

    This function updates analysis tracking fields from pipeline execution results.

    Args:
        entry: State entry to update
        results: Analysis pipeline results dictionary containing:
            - selected_modules or modules_requested: List of requested modules
            - modules_run: List of successfully completed modules
            - errors: List of error messages
            - duration: Execution duration in seconds
            - execution_order: Optional list of execution order

    Returns:
        Updated state entry with analysis fields populated
    """
    updated = entry.copy()

    # Extract results data
    modules_requested = results.get("selected_modules") or results.get(
        "modules_requested", []
    )
    modules_run = results.get("modules_run", [])
    errors = results.get("errors", [])
    duration = results.get("duration")
    execution_order = results.get("execution_order", [])

    # Update analysis fields
    updated["analysis_modules_requested"] = modules_requested
    updated["analysis_modules_run"] = modules_run
    updated["analysis_errors"] = errors
    updated["analysis_duration_seconds"] = duration
    updated["analysis_timestamp"] = datetime.now().isoformat()
    updated["analysis_execution_order"] = execution_order

    # Determine which modules failed
    # Modules that were requested but didn't run (and aren't in errors as dependency issues)
    modules_failed = []
    for module in modules_requested:
        if module not in modules_run:
            # Check if error message mentions this module
            module_failed = False
            for error in errors:
                if module in error:
                    module_failed = True
                    break
            if module_failed or not any(module in err for err in errors):
                # Module was requested but didn't run
                modules_failed.append(module)

    updated["analysis_modules_failed"] = modules_failed

    # Calculate analysis status
    if not modules_requested:
        updated["analysis_status"] = "not_started"
    elif errors and not modules_run:
        updated["analysis_status"] = "failed"
    elif set(modules_run) == set(modules_requested):
        updated["analysis_status"] = "completed"
    elif modules_run:
        updated["analysis_status"] = "partial"
    else:
        updated["analysis_status"] = "failed"

    # Update analysis_completed flag
    updated["analysis_completed"] = updated["analysis_status"] == "completed"

    # Update last_updated timestamp
    updated["last_updated"] = datetime.now().isoformat()

    return updated


def get_analysis_status(entry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get current analysis status summary from state entry.

    Args:
        entry: State entry to extract analysis status from

    Returns:
        Dictionary with analysis status summary:
        {
            "status": str,  # "completed", "partial", "failed", "not_started"
            "modules_requested": List[str],
            "modules_run": List[str],
            "modules_failed": List[str],
            "modules_pending": List[str],
            "has_errors": bool,
            "error_count": int,
            "duration_seconds": float or None,
            "timestamp": str or None,
            "completed": bool
        }
    """
    status = entry.get("analysis_status", "not_started")
    modules_requested = entry.get("analysis_modules_requested", [])
    modules_run = entry.get("analysis_modules_run", [])
    modules_failed = entry.get("analysis_modules_failed", [])
    errors = entry.get("analysis_errors", [])

    # Calculate pending modules (requested but not run and not failed)
    modules_pending = [
        m for m in modules_requested if m not in modules_run and m not in modules_failed
    ]

    return {
        "status": status,
        "modules_requested": modules_requested,
        "modules_run": modules_run,
        "modules_failed": modules_failed,
        "modules_pending": modules_pending,
        "has_errors": len(errors) > 0,
        "error_count": len(errors),
        "duration_seconds": entry.get("analysis_duration_seconds"),
        "timestamp": entry.get("analysis_timestamp"),
        "completed": entry.get("analysis_completed", False),
    }
