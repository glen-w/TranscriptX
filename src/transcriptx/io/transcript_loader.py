"""
Transcript loading utilities for TranscriptX.

This module provides standardized functions for loading transcript data
from various sources and formats, with consistent validation and error handling.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

# Avoid importing from transcriptx.core at top level to prevent circular import
# (core -> pipeline -> pipeline_context -> transcript_service -> transcript_loader).
# CanonicalTranscript is imported inside load_canonical_transcript().


def load_segments(path: str) -> List[Dict[str, Any]]:
    """
    Load and extract segments from a transcript JSON file.

    This function handles different JSON structures that might be present
    in transcript files. It can process both direct segment lists and
    nested structures with a 'segments' key. Also handles WhisperX format
    with words arrays.

    Args:
        path: Path to the transcript JSON file

    Returns:
        List of segment dictionaries containing transcript data

    Note:
        The function is flexible and can handle:
        - Files with {"segments": [...]} structure
        - Files that are direct lists of segments
        - WhisperX format with words arrays (extracts speaker from words)
        - Returns empty list for invalid formats

        This flexibility allows TranscriptX to work with transcripts
        from different sources and formats without requiring strict
        standardization of the input files.

        IMPORTANT: This function only handles JSON files. VTT files should
        be converted to JSON via transcript_importer.ensure_json_artifact()
        before reaching this function.
    """
    # Ensure we're only handling JSON files
    path_obj = Path(path)
    if path_obj.suffix.lower() != ".json":
        raise ValueError(
            f"load_segments() only handles JSON files, got: {path_obj.suffix}. "
            f"VTT files should be converted to JSON via transcript_importer.ensure_json_artifact() first."
        )

    # Try to resolve path if file doesn't exist (handles renamed files)
    resolved_path = path
    if not path_obj.exists():
        try:
            from transcriptx.core.utils._path_resolution import resolve_file_path
            from transcriptx.core.utils.logger import get_logger
            resolved_path = resolve_file_path(path, file_type="transcript")
            get_logger().debug(f"Resolved transcript path: {path} -> {resolved_path}")
        except FileNotFoundError:
            # If resolution fails, raise the original error with the original path
            raise FileNotFoundError(f"Transcript file not found: {path}")

    with open(resolved_path) as f:
        data = json.load(f)

    segments = []
    if isinstance(data, dict):
        segments = data.get("segments", [])
    elif isinstance(data, list):
        segments = data  # assume it's already a list of segments

    # Process segments to handle WhisperX format with words arrays
    processed_segments = []
    for segment in segments:
        if isinstance(segment, dict):
            # Check if this is a WhisperX format segment with words array
            if "words" in segment and "speaker" not in segment:
                # Extract speaker from words array (use most common speaker)
                words = segment.get("words", [])
                if words:
                    # Count speaker occurrences
                    speaker_counts = {}
                    for word in words:
                        if isinstance(word, dict) and "speaker" in word:
                            speaker = word["speaker"]
                            speaker_counts[speaker] = speaker_counts.get(speaker, 0) + 1

                    # Use the most common speaker
                    if speaker_counts:
                        most_common_speaker = max(
                            speaker_counts, key=speaker_counts.get
                        )
                        # Create a new segment with speaker field
                        processed_segment = segment.copy()
                        processed_segment["speaker"] = most_common_speaker
                        processed_segments.append(processed_segment)
                    else:
                        # No speaker found in words, assign a default speaker
                        processed_segment = segment.copy()
                        processed_segment["speaker"] = "UNKNOWN_SPEAKER"
                        processed_segments.append(processed_segment)
                else:
                    # No words array, assign a default speaker
                    processed_segment = segment.copy()
                    processed_segment["speaker"] = "UNKNOWN_SPEAKER"
                    processed_segments.append(processed_segment)
            else:
                processed_segments.append(segment)
        else:
            processed_segments.append(segment)

    return processed_segments


def extract_speaker_map_from_transcript(transcript_path: str) -> Dict[str, str]:
    """
    Extract speaker map from transcript JSON metadata.

    This is a pure function that reads the transcript JSON and returns the
    speaker_map field if present. Returns empty dict if not found or on error.
    """
    try:
        with open(transcript_path, "r") as f:
            data = json.load(f)
        speaker_map = data.get("speaker_map", {})
        return speaker_map if isinstance(speaker_map, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def extract_ignored_speakers_from_transcript(transcript_path: str | Path) -> List[str]:
    """
    Extract ignored speaker IDs from transcript JSON metadata.

    Returns a unique, stable-order list of string IDs.
    """
    try:
        data = load_transcript(str(transcript_path))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, dict):
        return []
    raw_ids = data.get("ignored_speakers") or []
    if not isinstance(raw_ids, list):
        return []
    normalized = [str(item) for item in raw_ids if item is not None]
    return list(dict.fromkeys(normalized))


def load_canonical_transcript(path: str) -> "CanonicalTranscript":
    """
    Load a transcript file and return a CanonicalTranscript instance.

    This does not change behavior for existing callers; it simply wraps
    load_segments() into the canonical in-memory representation.
    """
    from transcriptx.core.domain.canonical_transcript import CanonicalTranscript

    segments = load_segments(path)
    if not segments:
        raise ValueError(f"No segments found in transcript: {path}")
    return CanonicalTranscript.from_segments(segments)


def load_transcript(path: str) -> Any:
    """
    Load a complete transcript file as JSON.

    This function loads the entire transcript file without any processing,
    useful when you need access to the full file structure including
    metadata, configuration, or other non-segment data.

    Args:
        path: Path to the transcript JSON file

    Returns:
        The complete JSON data from the file

    Note:
        Unlike load_segments(), this function preserves the complete
        file structure, including any metadata, configuration, or
        additional fields that might be present in the transcript file.
        This is useful for modules that need access to file-level
        information or custom fields.
    """
    with open(path) as f:
        return json.load(f)


def load_transcript_data(
    transcript_path: str, skip_speaker_mapping: bool = False, batch_mode: bool = False
) -> tuple[List[Dict[str, Any]], str, str, Dict[str, str]]:
    """
    Load and validate transcript data with standardized error handling.

    This function provides a common interface for loading transcript data
    across all analysis modules, ensuring consistent validation and error handling.

    DEPRECATED: Use TranscriptService.load_transcript_data() instead for caching support.
    This function is kept for backward compatibility and delegates to the service.

    Args:
        transcript_path: Path to the transcript JSON file
        skip_speaker_mapping: Skip speaker mapping if already done (default: False)
        batch_mode: Whether running in batch mode (default: False)

    Returns:
        Tuple containing:
        - segments: List of transcript segments
        - base_name: Base name for file naming
        - transcript_dir: Output directory path
        - speaker_map: Speaker ID to name mapping

    Raises:
        FileNotFoundError: If transcript file doesn't exist
        ValueError: If transcript file is invalid or empty
        Exception: For other loading errors
    """
    # Delegate to service for consistency and caching
    from transcriptx.io.transcript_service import get_transcript_service

    service = get_transcript_service()
    return service.load_transcript_data(
        transcript_path,
        skip_speaker_mapping=skip_speaker_mapping,
        batch_mode=batch_mode,
    )
