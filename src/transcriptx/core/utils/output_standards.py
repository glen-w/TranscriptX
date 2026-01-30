"""
Output Standards and Utilities for TranscriptX.

This module defines standardized output structures and utilities for all analysis modules.
It ensures consistent organization of outputs across all modules with clear separation
between visual insights and raw data, as well as global vs per-speaker outputs.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import os

from transcriptx.utils.text_utils import is_named_speaker
from transcriptx.io import save_csv, save_json
from transcriptx.core.utils.artifact_writer import write_text
from transcriptx.core.utils.paths import OUTPUTS_DIR, DIARISED_TRANSCRIPTS_DIR
from transcriptx.core.utils.logger import get_logger

logger = get_logger()


@dataclass
class OutputStructure:
    """Standardized output structure for analysis modules."""

    # Base directories
    module_dir: Path
    data_dir: Path
    charts_dir: Path
    transcript_dir: Path  # Base transcript output directory

    # Global outputs (all speakers combined)
    global_data_dir: Path
    global_charts_dir: Path
    global_static_charts_dir: Path
    global_dynamic_charts_dir: Path

    # Per-speaker outputs
    speaker_data_dir: Path
    speaker_charts_dir: Path
    speaker_static_charts_dir: Path
    speaker_dynamic_charts_dir: Path

    def __post_init__(self):
        """Initialize output structure without creating directories.

        Directories will be created lazily when files are actually saved
        by save_global_data, save_speaker_data, save_global_chart, etc.
        This prevents creating empty directory structures when no outputs are generated.
        """
        # Do not create directories here - they will be created when files are saved
        pass


def create_standard_output_structure(
    transcript_dir: str, module_name: str
) -> OutputStructure:
    """
    Create standardized output directory structure for an analysis module.

    Args:
        transcript_dir: Base transcript output directory
        module_name: Name of the analysis module

    Returns:
        OutputStructure object with all directories created
    """
    # Validate that transcript_dir is in OUTPUTS_DIR to prevent creating directories
    # in wrong locations (e.g., data/transcripts/raw)
    transcript_dir_path = Path(transcript_dir).resolve()
    outputs_dir_path = Path(OUTPUTS_DIR).resolve()
    transcripts_dir_path = Path(DIARISED_TRANSCRIPTS_DIR).resolve()

    # Explicitly prevent creating directories in data/transcripts
    if str(transcript_dir_path).startswith(str(transcripts_dir_path)):
        logger.warning(
            f"⚠️ transcript_dir is in transcripts directory ({transcript_dir}), "
            f"which is not allowed. Redirecting to outputs directory."
        )
        # Extract base name from the path (last component)
        base_name = transcript_dir_path.name
        # Use OUTPUTS_DIR as the base to ensure correct location
        transcript_dir = str(outputs_dir_path / base_name)
        transcript_dir_path = Path(transcript_dir).resolve()

    # If transcript_dir is not in OUTPUTS_DIR, extract just the base name
    # This prevents accidentally creating directories in data/transcripts/raw
    if not str(transcript_dir_path).startswith(str(outputs_dir_path)):
        logger.warning(
            f"⚠️ transcript_dir is not in OUTPUTS_DIR ({transcript_dir}). "
            f"Extracting base name and redirecting to outputs directory."
        )
        # Extract base name from the path (last component)
        base_name = transcript_dir_path.name
        # Use OUTPUTS_DIR as the base to ensure correct location
        transcript_dir = str(outputs_dir_path / base_name)
        transcript_dir_path = Path(transcript_dir).resolve()
    else:
        # transcript_dir is already in OUTPUTS_DIR; keep as-is
        transcript_dir = str(transcript_dir_path)

    module_dir = transcript_dir_path / module_name

    # Main directories
    data_dir = module_dir / "data"
    charts_dir = module_dir / "charts"

    # Global outputs (all speakers combined)
    global_data_dir = data_dir / "global"
    global_charts_dir = charts_dir / "global"
    global_static_charts_dir = global_charts_dir / "static"
    global_dynamic_charts_dir = global_charts_dir / "dynamic"

    # Per-speaker outputs
    speaker_data_dir = data_dir / "speakers"
    speaker_charts_dir = charts_dir / "speakers"
    speaker_static_charts_dir = speaker_charts_dir
    speaker_dynamic_charts_dir = speaker_charts_dir

    return OutputStructure(
        module_dir=module_dir,
        data_dir=data_dir,
        charts_dir=charts_dir,
        transcript_dir=transcript_dir_path,  # Store the resolved transcript directory path
        global_data_dir=global_data_dir,
        global_charts_dir=global_charts_dir,
        global_static_charts_dir=global_static_charts_dir,
        global_dynamic_charts_dir=global_dynamic_charts_dir,
        speaker_data_dir=speaker_data_dir,
        speaker_charts_dir=speaker_charts_dir,
        speaker_static_charts_dir=speaker_static_charts_dir,
        speaker_dynamic_charts_dir=speaker_dynamic_charts_dir,
    )


def save_global_data(
    data: Any,
    output_structure: OutputStructure,
    base_name: str,
    filename: str,
    file_type: str = "json",
) -> Path:
    """
    Save global (all-speakers) data to standardized location.

    Args:
        data: Data to save
        output_structure: OutputStructure object
        base_name: Base name for the transcript
        filename: Filename (without extension)
        file_type: Type of file ("json" or "csv")

    Returns:
        Path to saved file
    """
    file_path = output_structure.global_data_dir / f"{base_name}_{filename}.{file_type}"

    # Ensure directory exists before saving
    file_path.parent.mkdir(parents=True, exist_ok=True)

    if file_type == "json":
        save_json(data, str(file_path))
    elif file_type == "csv":
        if isinstance(data, list) and data:
            save_csv(data, str(file_path))
        else:
            if isinstance(data, dict):
                rows = [[key, value] for key, value in data.items()]
            else:
                rows = [[data]]
            save_csv(rows, str(file_path))

    return file_path


def save_speaker_data(
    data: Any,
    output_structure: OutputStructure,
    base_name: str,
    speaker: str,
    filename: str,
    file_type: str = "json",
) -> Path:
    """
    Save per-speaker data to standardized location.

    Args:
        data: Data to save
        output_structure: OutputStructure object
        base_name: Base name for the transcript
        speaker: Speaker name
        filename: Filename (without extension)
        file_type: Type of file ("json" or "csv")

    Returns:
        Path to saved file
    """
    # Sanitize speaker name for filename
    if not is_named_speaker(speaker):
        return None
    safe_speaker = str(speaker).replace(" ", "_").replace("/", "_")
    file_path = (
        output_structure.speaker_data_dir
        / f"{base_name}_{safe_speaker}_{filename}.{file_type}"
    )

    # Ensure directory exists before saving
    file_path.parent.mkdir(parents=True, exist_ok=True)

    if file_type == "json":
        save_json(data, str(file_path))
    elif file_type == "csv":
        if isinstance(data, list) and data:
            save_csv(data, str(file_path))
        else:
            if isinstance(data, dict):
                rows = [[key, value] for key, value in data.items()]
            else:
                rows = [[data]]
            save_csv(rows, str(file_path))

    return file_path


def get_global_static_chart_path(
    output_structure: OutputStructure,
    base_name: str | None,
    filename: str,
    chart_type: str | None,
) -> Path:
    chart_dir = output_structure.global_static_charts_dir
    if chart_type:
        chart_dir = chart_dir / chart_type
    chart_dir.mkdir(parents=True, exist_ok=True)
    name = f"{base_name}_{filename}" if base_name else filename
    return chart_dir / f"{name}.png"


def get_global_dynamic_chart_path(
    output_structure: OutputStructure,
    base_name: str | None,
    filename: str,
    chart_type: str | None,
) -> Path:
    chart_dir = output_structure.global_dynamic_charts_dir
    if chart_type:
        chart_dir = chart_dir / chart_type
    chart_dir.mkdir(parents=True, exist_ok=True)
    name = f"{base_name}_{filename}" if base_name else filename
    return chart_dir / f"{name}.html"


def get_speaker_static_chart_path(
    output_structure: OutputStructure,
    base_name: str | None,
    speaker: str,
    filename: str,
    chart_type: str | None,
) -> Path | None:
    if not is_named_speaker(speaker):
        return None
    safe_speaker = str(speaker).replace(" ", "_").replace("/", "_")
    chart_dir = output_structure.speaker_static_charts_dir / safe_speaker / "static"
    if chart_type:
        chart_dir = chart_dir / chart_type
    chart_dir.mkdir(parents=True, exist_ok=True)
    name = f"{base_name}_{filename}" if base_name else filename
    return chart_dir / f"{name}.png"


def get_speaker_dynamic_chart_path(
    output_structure: OutputStructure,
    base_name: str | None,
    speaker: str,
    filename: str,
    chart_type: str | None,
) -> Path | None:
    if not is_named_speaker(speaker):
        return None
    safe_speaker = str(speaker).replace(" ", "_").replace("/", "_")
    chart_dir = output_structure.speaker_dynamic_charts_dir / safe_speaker / "dynamic"
    if chart_type:
        chart_dir = chart_dir / chart_type
    chart_dir.mkdir(parents=True, exist_ok=True)
    name = f"{base_name}_{filename}" if base_name else filename
    return chart_dir / f"{name}.html"


def save_global_chart(*args, **kwargs) -> Path:
    raise NotImplementedError(
        "save_global_chart() has been removed. Use OutputService.save_chart() instead."
    )


def save_speaker_chart(*args, **kwargs) -> Path:
    raise NotImplementedError(
        "save_speaker_chart() has been removed. Use OutputService.save_chart() instead."
    )




def create_summary_json(
    module_name: str,
    base_name: str,
    global_data: dict[str, Any],
    speaker_data: dict[str, Any],
    analysis_metadata: dict[str, Any],
    output_structure: OutputStructure,
) -> Path:
    """
    Create a comprehensive summary JSON file for the module.

    Args:
        module_name: Name of the analysis module
        base_name: Base name for the transcript
        global_data: Global analysis results
        speaker_data: Per-speaker analysis results
        analysis_metadata: Metadata about the analysis
        output_structure: OutputStructure object

    Returns:
        Path to saved summary file
    """
    summary = {
        "module": module_name,
        "transcript": base_name,
        "analysis_metadata": analysis_metadata,
        "global_results": global_data,
        "speaker_results": speaker_data,
        "output_structure": {
            "data_directory": str(output_structure.data_dir),
            "charts_directory": str(output_structure.charts_dir),
            "global_data_directory": str(output_structure.global_data_dir),
            "global_charts_directory": str(output_structure.global_charts_dir),
            "speaker_data_directory": str(output_structure.speaker_data_dir),
            "speaker_charts_directory": str(output_structure.speaker_charts_dir),
        },
    }

    summary_path = (
        output_structure.global_data_dir / f"{base_name}_{module_name}_summary.json"
    )
    save_json(summary, str(summary_path))
    return summary_path


def get_standard_file_patterns(base_name: str, module_name: str) -> dict[str, str]:
    """
    Get standard file naming patterns for consistency.

    Args:
        base_name: Base name for the transcript
        module_name: Name of the analysis module

    Returns:
        Dictionary of standard file patterns
    """
    return {
        "global_summary": f"{base_name}_{module_name}_summary",
        "global_data": f"{base_name}_{module_name}_global",
        "speaker_data": f"{base_name}_{module_name}_speaker",
        "speaker_chart": f"{base_name}_{module_name}_chart",
        "global_chart": f"{base_name}_{module_name}_global_chart",
    }


def create_readme_file(
    output_structure: OutputStructure,
    module_name: str,
    base_name: str,
    description: str,
) -> Path:
    """
    Create a README file for the module output directory.

    Args:
        output_structure: OutputStructure object
        module_name: Name of the analysis module
        base_name: Base name for the transcript
        description: Description of what the module does

    Returns:
        Path to the created README file
    """
    readme_path = output_structure.module_dir / "README.md"

    content = f"""# {module_name.replace('_', ' ').title()} Analysis

## Description
{description}

## Output Structure
- `data/global/`: Global analysis results (all speakers combined)
- `data/speakers/`: Per-speaker analysis results
- `charts/global/`: Global visualization charts
- `charts/speakers/`: Per-speaker visualization charts

## Files
This directory contains the analysis results for transcript: {base_name}

Generated by TranscriptX analysis pipeline.
"""

    write_text(readme_path, content)

    return readme_path


def cleanup_empty_directories(module_dir: Path) -> None:
    """
    Remove empty directories from a module's output structure.

    This function recursively removes empty directories to avoid cluttering
    the output with unnecessary empty folders.

    Args:
        module_dir: Path to the module directory to clean up
    """
    if not module_dir.exists():
        return

    # Walk through all subdirectories in reverse order (deepest first)
    for root, dirs, files in os.walk(module_dir, topdown=False):
        root_path = Path(root)

        # Check each subdirectory
        for dir_name in dirs:
            dir_path = root_path / dir_name

            # Remove directory if it's empty
            try:
                if not any(dir_path.iterdir()):
                    dir_path.rmdir()
                    print(f"[INFO] Removed empty directory: {dir_path}")
            except (OSError, PermissionError) as e:
                # Skip if we can't remove the directory
                print(f"[WARNING] Could not remove directory {dir_path}: {e}")


def cleanup_module_outputs(transcript_dir: Path, module_name: str) -> None:
    """
    Clean up empty directories for a specific module.

    Args:
        transcript_dir: Base transcript directory
        module_name: Name of the module to clean up
    """
    module_dir = transcript_dir / module_name
    cleanup_empty_directories(module_dir)
