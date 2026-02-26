"""
Core path utilities for TranscriptX.

This module contains the fundamental path generation and validation functions
that don't depend on path resolution or caching logic.
"""

import os
from pathlib import Path
from typing import Dict

from transcriptx.core.utils.paths import GROUP_OUTPUTS_DIR, OUTPUTS_DIR

_TRANSCRIPT_OUTPUT_OVERRIDES: Dict[str, str] = {}


def get_canonical_base_name(transcript_path: str) -> str:
    """
    Get canonical base name, stripping common suffixes if present.

    This ensures consistent base names regardless of file naming patterns.
    The canonical base name is used for output directories and file naming.

    Args:
        transcript_path: Path to the transcript JSON file

    Returns:
        Canonical base name without extension or common suffixes

    Example:
        >>> get_canonical_base_name("/path/to/meeting1.json")
        "meeting1"
        >>> get_canonical_base_name("/path/to/20251224205256.json")
        "20251224205256"
    """
    base_name = os.path.splitext(os.path.basename(transcript_path))[0]

    # Strip suffixes in order of specificity (longest first)
    suffixes = ["_transcript_diarised", "_transcript", "_diarised"]
    for suffix in suffixes:
        if base_name.endswith(suffix):
            base_name = base_name[: -len(suffix)]
            break

    return base_name


def is_canonical_transcript_filename(path: str | Path) -> bool:
    """
    Return True if the path has a canonical transcript filename.

    Canonical filenames end with *_transcriptx.json (primary) or *_canonical.json
    (migration alias). All other names are non-canonical; analysis will refuse
    them unless the user runs an import step or passes --accept-noncanonical.
    """
    name = os.path.basename(str(path))
    return name.endswith("_transcriptx.json") or name.endswith("_canonical.json")


def get_base_name(transcript_path: str) -> str:
    """
    Extract base name from transcript file path.

    This function returns the filename without extension.
    For canonical base names (without suffixes), use get_canonical_base_name().

    Args:
        transcript_path: Path to the transcript JSON file

    Returns:
        Base name without extension (e.g., "meeting1" from "meeting1.json")

    Example:
        >>> get_base_name("/path/to/meeting1.json")
        "meeting1"
        >>> get_base_name("/path/to/20251224205256.json")
        "20251224205256"
    """
    return os.path.splitext(os.path.basename(transcript_path))[0]


def get_transcript_dir(transcript_path: str) -> str:
    """
    Get the transcript output directory path.

    Uses canonical base name to ensure consistent directory naming.

    Args:
        transcript_path: Path to the transcript JSON file

    Returns:
        Path to the transcript's output directory in the outputs folder

    Example:
        >>> get_transcript_dir("/path/to/meeting1.json")
        "/path/to/outputs/meeting1"
        >>> get_transcript_dir("/path/to/20251224205256.json")
        "/path/to/outputs/20251224205256"
    """
    resolved = str(Path(transcript_path).resolve())
    if resolved in _TRANSCRIPT_OUTPUT_OVERRIDES:
        return _TRANSCRIPT_OUTPUT_OVERRIDES[resolved]
    base_name = get_canonical_base_name(transcript_path)
    return os.path.join(OUTPUTS_DIR, base_name)


def set_transcript_output_dir(transcript_path: str, output_dir: str) -> None:
    resolved = str(Path(transcript_path).resolve())
    _TRANSCRIPT_OUTPUT_OVERRIDES[resolved] = output_dir


def clear_transcript_output_dir(transcript_path: str) -> None:
    resolved = str(Path(transcript_path).resolve())
    _TRANSCRIPT_OUTPUT_OVERRIDES.pop(resolved, None)


def get_module_output_dir(transcript_path: str, module_name: str) -> str:
    """
    Get the output directory for a specific analysis module.

    Args:
        transcript_path: Path to the transcript JSON file
        module_name: Name of the analysis module

    Returns:
        Path to the module's output directory

    Example:
        >>> get_module_output_dir("/path/to/meeting1.json", "sentiment")
        "/path/to/meeting1/sentiment"
    """
    transcript_dir = get_transcript_dir(transcript_path)
    return os.path.join(transcript_dir, module_name)


def get_group_output_dir(group_uuid: str, run_id: str) -> str:
    """
    Get the group output directory path.

    Args:
        group_uuid: Stable identifier for the Group (UUID)
        run_id: Group analysis run identifier

    Returns:
        Path to the group output directory in outputs/groups
    """
    return os.path.join(GROUP_OUTPUTS_DIR, group_uuid, run_id)


def get_module_data_file(transcript_path: str, module_name: str, filename: str) -> str:
    """
    Get the path to a data file within a module's output directory.

    Args:
        transcript_path: Path to the transcript JSON file
        module_name: Name of the analysis module
        filename: Name of the data file

    Returns:
        Full path to the data file

    Example:
        >>> get_module_data_file("/path/to/meeting1.json", "sentiment", "summary.json")
        "/path/to/meeting1/sentiment/summary.json"
    """
    module_dir = get_module_output_dir(transcript_path, module_name)
    return os.path.join(module_dir, filename)


def get_enriched_transcript_path(transcript_path: str, module_name: str) -> str:
    """
    Get the path for an enriched transcript file with module-specific data.

    This function returns the standardized path for enriched transcripts,
    which should be saved in the module's global_data_dir for consistency.

    Args:
        transcript_path: Path to the original transcript JSON file
        module_name: Name of the analysis module

    Returns:
        Path to the enriched transcript file

    Example:
        >>> get_enriched_transcript_path("/path/to/meeting1.json", "sentiment")
        "/path/to/meeting1/sentiment/data/global/meeting1_with_sentiment.json"
    """
    base_name = get_base_name(transcript_path)
    transcript_dir = get_transcript_dir(transcript_path)
    # Use standardized path: transcript_dir/module_name/data/global/
    return os.path.join(
        transcript_dir,
        module_name,
        "data",
        "global",
        f"{base_name}_with_{module_name}.json",
    )


def get_enriched_transcript_path_legacy(transcript_path: str, module_name: str) -> str:
    """
    Get the legacy path for an enriched transcript file (for backward compatibility).

    This function returns the old path format for enriched transcripts.
    Use get_enriched_transcript_path() for new code.

    Args:
        transcript_path: Path to the original transcript JSON file
        module_name: Name of the analysis module

    Returns:
        Path to the enriched transcript file in legacy format

    Example:
        >>> get_enriched_transcript_path_legacy("/path/to/meeting1.json", "sentiment")
        "/path/to/meeting1/sentiment/meeting1_with_sentiment.json"
    """
    base_name = get_base_name(transcript_path)
    module_dir = get_module_output_dir(transcript_path, module_name)
    return os.path.join(module_dir, f"{base_name}_with_{module_name}.json")


def find_enriched_transcript(transcript_path: str, module_name: str) -> str:
    """
    Find an enriched transcript file, checking both new and legacy locations.

    This function first checks the standardized location, then falls back
    to the legacy location for backward compatibility.

    Args:
        transcript_path: Path to the original transcript JSON file
        module_name: Name of the analysis module

    Returns:
        Path to the enriched transcript file if found, None otherwise
    """
    # Check standardized location first
    standardized_path = get_enriched_transcript_path(transcript_path, module_name)
    if os.path.exists(standardized_path):
        return standardized_path

    # Fall back to legacy location
    legacy_path = get_enriched_transcript_path_legacy(transcript_path, module_name)
    if os.path.exists(legacy_path):
        return legacy_path

    return None


def ensure_output_dirs(transcript_path: str, module_name: str) -> Dict[str, str]:
    """
    Create and return all standard output directories for a module.

    This function creates the standard directory structure used by analysis modules:
    - module_dir: Main module output directory
    - data_dir: For data files (JSON, CSV)
    - charts_dir: For visualization files (PNG, HTML)
    - global_data_dir: For transcript-wide data
    - global_charts_dir: For transcript-wide visualizations
    - speaker_data_dir: For per-speaker data
    - speaker_charts_dir: For per-speaker visualizations

    Args:
        transcript_path: Path to the transcript JSON file
        module_name: Name of the analysis module

    Returns:
        Dictionary mapping directory type to path

    Example:
        >>> dirs = ensure_output_dirs("/path/to/meeting1.json", "sentiment")
        >>> dirs["module_dir"]
        "/path/to/meeting1/sentiment"
        >>> dirs["data_dir"]
        "/path/to/meeting1/sentiment/data"
    """
    module_dir = get_module_output_dir(transcript_path, module_name)
    data_dir = os.path.join(module_dir, "data")
    charts_dir = os.path.join(module_dir, "charts")
    global_data_dir = os.path.join(data_dir, "global")
    global_charts_dir = os.path.join(charts_dir, "global")
    speaker_data_dir = os.path.join(data_dir, "speakers")
    speaker_charts_dir = os.path.join(charts_dir, "speakers")

    # Create all directories
    for directory in [
        module_dir,
        data_dir,
        charts_dir,
        global_data_dir,
        global_charts_dir,
        speaker_data_dir,
        speaker_charts_dir,
    ]:
        os.makedirs(directory, exist_ok=True)

    return {
        "module_dir": module_dir,
        "data_dir": data_dir,
        "charts_dir": charts_dir,
        "global_data_dir": global_data_dir,
        "global_charts_dir": global_charts_dir,
        "speaker_data_dir": speaker_data_dir,
        "speaker_charts_dir": speaker_charts_dir,
    }


def get_stats_summary_path(transcript_path: str) -> str:
    """
    Get the path for the comprehensive stats summary file.

    Args:
        transcript_path: Path to the transcript JSON file

    Returns:
        Path to the stats summary file

    Example:
        >>> get_stats_summary_path("/path/to/meeting1.json")
        "/path/to/meeting1/stats/meeting1_comprehensive_summary.txt"
    """
    base_name = get_base_name(transcript_path)
    transcript_dir = get_transcript_dir(transcript_path)
    stats_dir = os.path.join(transcript_dir, "stats")
    summary_dir = os.path.join(stats_dir, "summary")

    # Ensure directories exist
    os.makedirs(summary_dir, exist_ok=True)

    return os.path.join(summary_dir, f"{base_name}_comprehensive_summary.txt")


def get_html_summary_path(transcript_path: str) -> str:
    """
    Get the path for the HTML summary file.

    Args:
        transcript_path: Path to the transcript JSON file

    Returns:
        Path to the HTML summary file

    Example:
        >>> get_html_summary_path("/path/to/meeting1.json")
        "/path/to/meeting1/meeting1_comprehensive_summary.html"
    """
    base_name = get_base_name(transcript_path)
    transcript_dir = get_transcript_dir(transcript_path)
    return os.path.join(transcript_dir, f"{base_name}_comprehensive_summary.html")


def validate_transcript_path(transcript_path: str) -> bool:
    """
    Validate that a transcript path is properly formatted and exists.

    Args:
        transcript_path: Path to validate

    Returns:
        True if valid, False otherwise
    """
    if not transcript_path:
        return False

    if not os.path.exists(transcript_path):
        return False

    if not transcript_path.lower().endswith(".json"):
        return False

    return True


def get_relative_output_path(transcript_path: str, target_path: str) -> str:
    """
    Get a relative path from the transcript directory to a target file.

    Args:
        transcript_path: Path to the transcript JSON file
        target_path: Path to the target file

    Returns:
        Relative path from transcript directory to target file
    """
    transcript_dir = get_transcript_dir(transcript_path)
    return os.path.relpath(target_path, transcript_dir)
