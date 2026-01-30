"""
File I/O utilities for TranscriptX.

This module provides standardized functions for saving data in various formats
with consistent error handling and data serialization.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Callable

import numpy as np
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import DIARISED_TRANSCRIPTS_DIR
from transcriptx.core.utils.artifact_writer import write_csv, write_json, write_text

logger = get_logger()


def _validate_directory_creation(path: str) -> bool:
    """
    Validate that we're not creating unwanted subdirectories in transcripts folder.

    Only allows 'readable' subdirectory in transcripts folder. Prevents creation
    of other subdirectories like 'raw' in data/transcripts.

    Args:
        path: File path where directory will be created

    Returns:
        True if directory creation is allowed, False otherwise
    """
    try:
        path_obj = Path(path).resolve()
        transcripts_dir = Path(DIARISED_TRANSCRIPTS_DIR).resolve()
        dir_to_create = path_obj.parent

        # Check if the directory to create is within transcripts directory
        # and is not the transcripts directory itself
        if (
            dir_to_create != transcripts_dir
            and transcripts_dir in dir_to_create.parents
        ):
            # Check if it's the readable subdirectory (allowed)
            if (
                dir_to_create.parent == transcripts_dir
                and dir_to_create.name == "readable"
            ):
                return True

            # Any other subdirectory in transcripts is not allowed
            if dir_to_create.parent == transcripts_dir:
                logger.warning(
                    f"⚠️ Attempted to create invalid subdirectory '{dir_to_create.name}' "
                    f"in transcripts folder. Only 'readable' subdirectory is allowed. "
                    f"Blocking directory creation for path: {path}"
                )
                return False
    except (OSError, ValueError) as e:
        # If path resolution fails, allow it (might be a relative path issue)
        logger.debug(f"Path resolution issue in directory validation: {e}")

    return True


def save_json(data: Dict[str, Any], path: str) -> None:
    """
    Save data to a JSON file with proper serialization.

    This function handles numpy types and other non-serializable objects
    by converting them to standard Python types.

    Args:
        data: Dictionary or list to save
        path: Path where the file should be saved
    """

    def convert_np(obj: Any) -> Any:
        """Convert numpy types to standard Python types."""
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        return str(obj) if hasattr(obj, "__str__") else obj

    # Validate directory creation before creating it
    if not _validate_directory_creation(path):
        # If validation fails, raise error to prevent unwanted directory creation
        raise ValueError(
            f"Cannot save file to {path}: Invalid subdirectory in transcripts folder. "
            f"Only 'readable' subdirectory is allowed."
        )

    payload = json.loads(json.dumps(data, default=convert_np))
    write_json(path, payload, indent=2, ensure_ascii=False)

    logger.debug(f"Saved JSON data to: {path}")


def save_csv(rows: List[List], path: str, header: List[str] | None = None) -> None:
    """
    Save data to a CSV file.

    Args:
        rows: List of rows to save (each row is a list of values)
        path: Path where the file should be saved
        header: Optional header row
    """
    # Validate directory creation before creating it
    if not _validate_directory_creation(path):
        # If validation fails, raise error to prevent unwanted directory creation
        raise ValueError(
            f"Cannot save file to {path}: Invalid subdirectory in transcripts folder. "
            f"Only 'readable' subdirectory is allowed."
        )

    write_csv(path, rows, header=header)

    logger.debug(f"Saved CSV data to: {path}")


def save_transcript(data: List[Dict[str, Any]], path: str) -> None:
    """
    Save transcript data to a JSON file.

    This function saves transcript segments in the standard format,
    wrapping them in a 'segments' key if needed.

    Args:
        data: List of transcript segments or complete transcript data
        path: Path where the file should be saved
    """
    # Validate directory creation before creating it
    if not _validate_directory_creation(path):
        # If validation fails, raise error to prevent unwanted directory creation
        raise ValueError(
            f"Cannot save file to {path}: Invalid subdirectory in transcripts folder. "
            f"Only 'readable' subdirectory is allowed."
        )

    content = {"segments": data} if isinstance(data, list) else data
    write_json(path, content, indent=2, ensure_ascii=False)

    logger.debug(f"Saved transcript to: {path}")


def write_transcript_files(
    segments: List[Dict[str, Any]],
    speaker_map: Dict[str, str] | None = None,
    base_name: str = "",
    out_dir: str = "",
    format_time_func: Callable[[float], str] | None = None,
) -> tuple[str, str]:
    """
    Write transcript files in both TXT and CSV formats.

    Uses database-driven speaker identification. The speaker field in segments
    should already contain the display name. speaker_map parameter is deprecated
    and only used as a fallback for backward compatibility.

    Args:
        segments: List of transcript segments (should have 'speaker' field with display name)
        speaker_map: Deprecated - mapping from speaker IDs to human-readable names (optional, for backward compatibility)
        base_name: Base name for file naming
        out_dir: Output directory
        format_time_func: Function to format timestamps

    Returns:
        Tuple of (transcript_txt_path, transcript_csv_path)
    """
    if format_time_func is None:
        from transcriptx.utils.text_utils import format_time

        format_time_func = format_time

    transcript_path = os.path.join(out_dir, f"{base_name}-transcript.txt")
    csv_path = os.path.join(out_dir, f"{base_name}-transcript.csv")

    rows: List[List[str]] = [["Speaker", "Timestamp", "Text"]]
    prev_speaker = None
    buffer: List[str] = []
    start_time = None
    text_lines: List[str] = []

    # Import speaker extraction utilities for fallback
    try:
        from transcriptx.core.utils.speaker_extraction import (
            extract_speaker_info,
            get_speaker_display_name,
        )
        from transcriptx.utils.text_utils import is_named_speaker

        use_speaker_extraction = True
    except ImportError:
        use_speaker_extraction = False
        logger.warning(
            "Speaker extraction utilities not available, using basic fallback"
        )

    for seg in segments:
        # Get speaker name - segments should already have display name in 'speaker' field
        speaker_field = seg.get("speaker", "")

        # Use speaker field directly if it looks like a display name
        if speaker_field and (
            not use_speaker_extraction or is_named_speaker(str(speaker_field))
        ):
            name = str(speaker_field)
        elif use_speaker_extraction:
            # Fallback: try to extract speaker info if speaker field is ID-like
            speaker_info = extract_speaker_info(seg)
            if speaker_info:
                name = get_speaker_display_name(
                    speaker_info.grouping_key, [seg], segments
                )
            else:
                name = str(speaker_field) if speaker_field else "Unknown"
        elif speaker_map:
            # Legacy fallback: use speaker_map if provided
            speaker_key = str(speaker_field)
            name = speaker_map.get(speaker_key, speaker_key)
        else:
            name = str(speaker_field) if speaker_field else "Unknown"

        text = seg.get("text", "").strip()
        pause = seg.get("pause", 0)
        timestamp = format_time_func(seg.get("start", 0))

        rows.append([name, timestamp, text])

        if name != prev_speaker:
            if prev_speaker and buffer:
                text_lines.append(f"\n🗣️ {prev_speaker} ⏱️ {start_time}\n")
                text_lines.extend(buffer)
                text_lines.append("\n")
                buffer = []
            prev_speaker = name
            start_time = timestamp

        if pause >= 2:
            buffer.append(f"\n⏸️  {int(pause)} sec pause\n")

        buffer.append(text.strip() + "\n\n")

    if prev_speaker and buffer:
        text_lines.append(f"\n🗣️ {prev_speaker} ⏱️ {start_time}\n")
        text_lines.extend(buffer)
        text_lines.append("\n")

    write_csv(csv_path, rows[1:], header=rows[0])
    write_text(transcript_path, "".join(text_lines))

    logger.debug(f"Saved transcript files: {transcript_path}, {csv_path}")
    return transcript_path, csv_path
