"""
Human-friendly transcript output module.

This module generates human-friendly transcript files in both text and CSV formats.
"""

import os
from pathlib import Path
from typing import Any

from transcriptx.core.utils.logger import (
    get_logger,
    log_analysis_complete,
    log_analysis_error,
    log_analysis_start,
)
from transcriptx.utils.text_utils import format_time
from transcriptx.core.utils.notifications import notify_user
from transcriptx.io import load_segments
from transcriptx.io.file_io import write_transcript_files
from transcriptx.core.utils.paths import OUTPUTS_DIR, DIARISED_TRANSCRIPTS_DIR


def generate_human_friendly_transcript(
    segments: list, base_name: str, transcript_dir: str, speaker_map: dict | None = None
) -> dict[str, Any]:
    """
    Generate human-friendly transcript files.

    Uses database-driven speaker identification. The speaker field in segments
    should already contain the display name. speaker_map parameter is deprecated
    and only used as a fallback for backward compatibility.

    Args:
        segments: List of transcript segments (should have 'speaker' field with display name)
        base_name: Base name for output files
        transcript_dir: Directory to save outputs
        speaker_map: Deprecated - Speaker ID to name mapping (optional, for backward compatibility)

    Returns:
        Dictionary containing results
    """
    logger = get_logger()
    logger.info(f"Generating human-friendly transcript for {base_name}")

    # Ensure transcript_dir is in the outputs directory, not in data/transcripts
    # This prevents accidentally creating directories in the wrong location (e.g., data/transcripts/raw)
    transcript_dir_path = Path(transcript_dir).resolve()
    outputs_dir_path = Path(OUTPUTS_DIR).resolve()
    transcripts_dir_path = Path(DIARISED_TRANSCRIPTS_DIR).resolve()

    # Explicitly prevent creating directories in data/transcripts
    if str(transcript_dir_path).startswith(str(transcripts_dir_path)):
        logger.warning(
            f"⚠️ transcript_dir is in transcripts directory ({transcript_dir}), "
            f"which is not allowed. Redirecting to outputs directory."
        )
        transcript_dir = os.path.join(OUTPUTS_DIR, base_name)
        transcript_dir_path = Path(transcript_dir).resolve()

    # Ensure transcript_dir is in the outputs directory
    if not str(transcript_dir_path).startswith(str(outputs_dir_path)):
        logger.warning(
            f"⚠️ transcript_dir is not in outputs directory: {transcript_dir}. "
            f"Correcting to outputs directory."
        )
        transcript_dir = os.path.join(OUTPUTS_DIR, base_name)

    try:
        # Generate the transcript files to the transcripts subdirectory
        transcripts_dir = os.path.join(transcript_dir, "transcripts")
        os.makedirs(transcripts_dir, exist_ok=True)
        txt_path, csv_path = write_transcript_files(
            segments, speaker_map, base_name, transcripts_dir, format_time
        )

        # Extract unique speakers using database-driven approach
        from transcriptx.core.utils.speaker_extraction import get_unique_speakers
        from transcriptx.utils.text_utils import is_named_speaker

        unique_speakers = get_unique_speakers(segments)
        speaker_names = sorted(
            [name for name in set(unique_speakers.values()) if is_named_speaker(name)]
        )

        summary_data = {
            "transcript_file": txt_path,
            "csv_file": csv_path,
            "total_segments": len(segments),
            "speakers": speaker_names,
            "duration_minutes": (
                max(seg.get("end", 0) for seg in segments) / 60 if segments else 0
            ),
        }

        logger.info(f"Human-friendly transcript generated successfully: {txt_path}")
        notify_user(
            "✅ Generated human-friendly transcript",
            technical=False,
            section="transcript_output",
        )

        return {
            "status": "success",
            "transcript_file": txt_path,
            "csv_file": csv_path,
            "summary": summary_data,
        }

    except Exception as e:
        error_msg = f"Failed to generate human-friendly transcript: {str(e)}"
        logger.error(error_msg)
        notify_user(f"❌ {error_msg}", technical=True, section="transcript_output")
        log_analysis_error("transcript_output", transcript_dir, e)
        raise


def generate_human_friendly_transcript_from_file(
    path: str, batch_mode: bool = False
) -> dict[str, Any]:
    """
    Generate human-friendly transcript from file.

    Uses database-driven speaker identification. No speaker_map file is needed.

    Args:
        path: Path to transcript JSON file
        batch_mode: Deprecated - no longer used (kept for backward compatibility)

    Returns:
        Dictionary containing results
    """
    logger = get_logger()
    logger.info(f"Starting human-friendly transcript generation for {path}")

    # Get base name and output directory
    base_name = os.path.splitext(os.path.basename(path))[0]
    from transcriptx.core.utils.path_utils import get_transcript_dir

    transcript_dir = get_transcript_dir(path)

    # Load transcript data
    segments = load_segments(path)

    # Run the analysis (no speaker_map needed - uses database-driven approach)
    log_analysis_start("transcript_output", path)

    try:
        results = generate_human_friendly_transcript(
            segments, base_name, transcript_dir, speaker_map=None
        )
        log_analysis_complete("transcript_output", path)
        return results
    except Exception as e:
        log_analysis_error("transcript_output", path, e)
        raise


def generate_transcript_output_from_file(transcript_path: str) -> None:
    """
    Generate transcript output from file.

    This function provides the interface expected by the module registry
    for the transcript_output module.

    Uses database-driven speaker identification. No speaker_map is needed.

    Args:
        transcript_path: Path to the transcript JSON file
    """
    from transcriptx.core.analysis.common import load_transcript_data

    segments, base_name, transcript_dir, speaker_map = load_transcript_data(
        transcript_path
    )
    # speaker_map is deprecated but still returned by load_transcript_data for backward compatibility
    # Pass None to use database-driven approach
    generate_human_friendly_transcript(
        segments, base_name, transcript_dir, speaker_map=None
    )
