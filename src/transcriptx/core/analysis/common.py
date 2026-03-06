"""
Common utilities for TranscriptX analysis modules.

This module provides shared utilities and helper functions that are commonly
used across all analysis modules, reducing code duplication and ensuring
consistency in data handling, validation, and output generation.

Key Features:
- Standardized segment loading with validation
- Speaker map loading wrapper
- Output structure creation wrapper
- Data serialization helpers
- Common validation functions
- Shared configuration utilities
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Union

from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.artifact_writer import write_json, write_text
from transcriptx.core.utils.path_utils import (
    ensure_output_dirs,
)

# Note: load_segments and load_or_create_speaker_map are available via transcriptx.io
# but not imported here to avoid circular dependencies
# Import them lazily in functions that need them

logger = get_logger()


def load_transcript_data(
    transcript_path: str, skip_speaker_mapping: bool = False, batch_mode: bool = False
) -> tuple[List[Dict[str, Any]], str, str, Dict[str, str]]:
    """
    Load and validate transcript data with standardized error handling.

    This function delegates to the I/O service layer for consistency and caching.
    It provides a common interface for loading transcript data across all
    analysis modules, ensuring consistent validation and error handling.

    Note: speaker_map return value is deprecated. Use database-driven speaker
    identification via speaker_extraction utilities instead. The speaker_map
    is returned for backward compatibility only and may be removed in a future version.

    Args:
        transcript_path: Path to the transcript JSON file
        skip_speaker_mapping: Deprecated - no longer used (kept for backward compatibility)
        batch_mode: Whether running in batch mode (default: False)

    Returns:
        Tuple containing:
        - segments: List of transcript segments (with speaker_db_id for database-driven identification)
        - base_name: Base name for file naming
        - transcript_dir: Output directory path
        - speaker_map: Deprecated - Dictionary mapping grouping_key to display_name (for backward compatibility only)

    Raises:
        FileNotFoundError: If transcript file doesn't exist
        ValueError: If transcript file is invalid or empty
        Exception: For other loading errors
    """
    import warnings

    # Delegate to I/O service for consistency and caching
    from transcriptx.io.transcript_service import get_transcript_service

    service = get_transcript_service()
    segments, base_name, transcript_dir, speaker_map = service.load_transcript_data(
        transcript_path,
        skip_speaker_mapping=skip_speaker_mapping,
        batch_mode=batch_mode,
    )

    # Issue deprecation warning if speaker_map is accessed
    # (We can't detect actual usage, but we can warn that it's deprecated)
    if speaker_map:
        warnings.warn(
            "speaker_map return value from load_transcript_data() is deprecated. "
            "Use database-driven speaker identification via speaker_extraction utilities instead. "
            "The speaker field in segments already contains display names.",
            DeprecationWarning,
            stacklevel=2,
        )

    return segments, base_name, transcript_dir, speaker_map


def create_module_output_structure(
    transcript_path: str, module_name: str
) -> Dict[str, str]:
    """
    Create standardized output structure for an analysis module.

    This function creates the standard directory structure used by all
    analysis modules, ensuring consistency across the codebase.

    Args:
        transcript_path: Path to the transcript JSON file
        module_name: Name of the analysis module

    Returns:
        Dictionary mapping directory type to path
    """
    return ensure_output_dirs(transcript_path, module_name)


def save_analysis_data(
    data: Dict[str, Any],
    output_structure: Dict[str, str],
    base_name: str,
    filename: str,
    format_type: str = "json",
) -> str:
    """
    Save analysis data in the specified format.

    Args:
        data: Data to save
        output_structure: Output directory structure
        base_name: Base name for file naming
        filename: Name of the file (without extension)
        format_type: Format to save in ("json", "csv", "txt")

    Returns:
        Path to the saved file
    """
    if format_type == "json":
        file_path = os.path.join(
            output_structure["data_dir"], f"{base_name}_{filename}.json"
        )
        write_json(file_path, data, indent=2, ensure_ascii=False)
    elif format_type == "csv":
        file_path = os.path.join(
            output_structure["data_dir"], f"{base_name}_{filename}.csv"
        )
        from transcriptx.io import save_csv

        if isinstance(data, list):
            save_csv(data, file_path)
        elif isinstance(data, dict):
            rows = [[key, value] for key, value in data.items()]
            save_csv(rows, file_path, header=["key", "value"])
        else:
            save_csv([[data]], file_path)
    elif format_type == "txt":
        file_path = os.path.join(
            output_structure["data_dir"], f"{base_name}_{filename}.txt"
        )
        if isinstance(data, dict):
            content = (
                "\n".join([f"{key}: {value}" for key, value in data.items()]) + "\n"
            )
        else:
            content = str(data)
        write_text(file_path, content)
    else:
        raise ValueError(f"Unsupported format type: {format_type}")

    logger.debug(f"Saved analysis data to: {file_path}")
    return file_path


def validate_segments(segments: List[Dict[str, Any]]) -> bool:
    """
    Validate that segments have the required structure.

    Args:
        segments: List of transcript segments

    Returns:
        True if valid, False otherwise
    """
    if not segments:
        return False

    required_fields = ["speaker", "text"]
    for segment in segments:
        if not isinstance(segment, dict):
            return False
        for field in required_fields:
            if field not in segment:
                return False

    return True


def get_speaker_text_by_speaker(
    segments: List[Dict[str, Any]], speaker_map: Dict[str, str] = None
) -> Dict[Union[str, int], List[str]]:
    """
    Extract and group text by speaker from transcript segments.

    This is a common operation across many analysis modules.
    Uses speaker_db_id for grouping when available to distinguish speakers with same name.

    Args:
        segments: List of transcript segments
        speaker_map: Speaker ID to name mapping (deprecated, kept for backward compatibility)

    Returns:
        Dictionary mapping grouping_key (db_id or name) to lists of text segments
    """
    from transcriptx.core.utils.speaker_extraction import group_segments_by_speaker

    # Group segments by speaker using speaker_db_id when available
    grouped_segments = group_segments_by_speaker(segments)

    # Extract text for each speaker group
    result: Dict[Union[str, int], List[str]] = {}
    for grouping_key, segs in grouped_segments.items():
        texts = [seg.get("text", "") for seg in segs if seg.get("text")]
        if texts:
            result[grouping_key] = texts

    return result


def get_module_config(module_name: str) -> Dict[str, Any]:
    """
    Get configuration for a specific analysis module.

    Args:
        module_name: Name of the analysis module

    Returns:
        Dictionary containing module-specific configuration
    """
    config = get_config()

    # Get module-specific config if it exists
    if hasattr(config, module_name):
        return getattr(config, module_name)

    # Return default config
    return {}


def create_analysis_summary(
    module_name: str,
    base_name: str,
    output_structure: Dict[str, str],
    results: Dict[str, Any],
    errors: List[str] = None,
) -> Dict[str, Any]:
    """
    Create a standardized analysis summary.

    Args:
        module_name: Name of the analysis module
        base_name: Base name for file naming
        output_structure: Output directory structure
        results: Analysis results
        errors: List of errors (if any)

    Returns:
        Dictionary containing analysis summary
    """
    summary = {
        "module": module_name,
        "transcript": base_name,
        "timestamp": str(Path().cwd()),
        "output_directory": output_structure["module_dir"],
        "status": "success" if not errors else "partial",
        "results": results,
    }

    if errors:
        summary["errors"] = errors

    return summary


def save_analysis_summary(
    summary: Dict[str, Any], output_structure: Dict[str, str], base_name: str
) -> str:
    """
    Save analysis summary to file.

    Args:
        summary: Analysis summary dictionary
        output_structure: Output directory structure
        base_name: Base name for file naming

    Returns:
        Path to the saved summary file
    """
    summary_path = os.path.join(
        output_structure["data_dir"], f"{base_name}_{summary['module']}_summary.json"
    )

    write_json(summary_path, summary, indent=2, ensure_ascii=False)

    logger.debug(f"Saved analysis summary to: {summary_path}")
    return summary_path


def log_analysis_start(module_name: str, transcript_path: str) -> None:
    """Log the start of an analysis module."""
    logger.info(f"Starting {module_name} analysis for {transcript_path}")


def log_analysis_complete(module_name: str, transcript_path: str) -> None:
    """Log the completion of an analysis module."""
    logger.info(f"Completed {module_name} analysis for {transcript_path}")


def log_analysis_error(module_name: str, transcript_path: str, error: str) -> None:
    """Log an error in an analysis module."""
    logger.error(f"Error in {module_name} analysis for {transcript_path}: {error}")


def ensure_directory_exists(directory_path: str) -> None:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        directory_path: Path to the directory
    """
    os.makedirs(directory_path, exist_ok=True)
    logger.debug(f"Ensured directory exists: {directory_path}")


def get_file_size_mb(file_path: str) -> float:
    """
    Get file size in megabytes.

    Args:
        file_path: Path to the file

    Returns:
        File size in megabytes
    """
    if not os.path.exists(file_path):
        return 0.0

    size_bytes = os.path.getsize(file_path)
    return size_bytes / (1024 * 1024)


def clean_text_for_analysis(text: str) -> str:
    """
    Clean text for analysis by removing common artifacts.

    Args:
        text: Raw text to clean

    Returns:
        Cleaned text
    """
    if not text:
        return ""

    # Remove extra whitespace
    text = " ".join(text.split())

    # Remove common artifacts (can be extended)
    artifacts = ["[inaudible]", "[unclear]", "[crosstalk]"]
    for artifact in artifacts:
        text = text.replace(artifact, "")

    return text.strip()
