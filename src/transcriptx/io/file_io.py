"""
File I/O utilities for TranscriptX.

This module provides standardized functions for saving data in various formats
with consistent error handling and data serialization.
"""

import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping

import numpy as np
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import DIARISED_TRANSCRIPTS_DIR
from transcriptx.core.utils.artifact_writer import write_csv, write_json, write_text
from transcriptx.io.srt_writer import write_srt_file
from transcriptx.io.vtt_writer import write_vtt_file

logger = get_logger()


def convert_np(obj: Any) -> Any:
    """Convert numpy types to standard Python types for JSON serialization."""
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    return str(obj) if hasattr(obj, "__str__") else obj


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


def _resolve_segment_speaker_name(
    seg: Mapping[str, Any],
    segments: List[Dict[str, Any]],
    speaker_map: Dict[str, str] | None = None,
) -> str:
    """Resolve the display speaker name used by transcript text-like outputs."""
    from transcriptx.core.utils.speaker_extraction import resolve_segment_speaker_label

    return resolve_segment_speaker_label(dict(seg), segments, speaker_map)


def write_transcript_files(
    segments: List[Dict[str, Any]],
    speaker_map: Dict[str, str] | None = None,
    base_name: str = "",
    out_dir: str = "",
    format_time_func: Callable[[float], str] | None = None,
) -> tuple[str, str, str, str]:
    """
    Write transcript files in TXT, CSV, SRT, and WebVTT formats.

    Uses segment-based speaker identification. The speaker field in segments
    should already contain the display name. speaker_map parameter is deprecated
    and only used as a fallback for backward compatibility.

    Args:
        segments: List of transcript segments (should have 'speaker' field with display name)
        speaker_map: Deprecated - mapping from speaker IDs to human-readable names (optional, for backward compatibility)
        base_name: Base name for file naming
        out_dir: Output directory
        format_time_func: Function to format timestamps

    Returns:
        Tuple of (transcript_txt_path, transcript_csv_path, transcript_srt_path,
        transcript_vtt_path)
    """
    if format_time_func is None:
        from transcriptx.utils.text_utils import format_time

        format_time_func = format_time

    transcript_path = os.path.join(out_dir, f"{base_name}-transcript.txt")
    csv_path = os.path.join(out_dir, f"{base_name}-transcript.csv")
    srt_path = os.path.join(out_dir, f"{base_name}-transcript.srt")
    vtt_path = os.path.join(out_dir, f"{base_name}-transcript.vtt")

    rows: List[List[str]] = [["Speaker", "Timestamp", "Text"]]
    prev_speaker = None
    buffer: List[str] = []
    start_time = None
    text_lines: List[str] = []

    for seg in segments:
        name = _resolve_segment_speaker_name(seg, segments, speaker_map)

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

    def _resolve_speaker(seg: Mapping[str, Any]) -> str:
        return _resolve_segment_speaker_name(seg, segments, speaker_map)

    write_csv(csv_path, rows[1:], header=rows[0])
    write_text(transcript_path, "".join(text_lines))
    write_srt_file(
        segments,
        srt_path,
        speaker_map=speaker_map,
        resolve_speaker=_resolve_speaker,
    )
    write_vtt_file(
        segments,
        vtt_path,
        speaker_map=speaker_map,
        resolve_speaker=_resolve_speaker,
    )

    logger.debug(
        f"Saved transcript files: {transcript_path}, {csv_path}, {srt_path}, {vtt_path}"
    )
    return transcript_path, csv_path, srt_path, vtt_path
