"""
Input validation utilities for TranscriptX.

This module provides comprehensive validation functions for all inputs
to ensure data integrity and prevent crashes from invalid data.
"""

import json
import os
from pathlib import Path
from typing import Any

from transcriptx.core.utils.logger import log_info, log_warning
from transcriptx.core.utils.paths import (
    OUTPUTS_DIR,
    RECORDINGS_DIR,
    DIARISED_TRANSCRIPTS_DIR,
)


def normalize_segment_speakers(segments: list) -> None:
    """
    Fill missing top-level 'speaker' on segments in place.

    Uses the previous segment's speaker, or the first word-level speaker
    in the segment, or "unknown" if neither is available. Used by
    TranscriptService for cache and DB-loaded segments that may not
    have been through the file loader (which already fills speaker).
    """
    prev_speaker: str = "unknown"
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        if "speaker" in segment and isinstance(segment["speaker"], str):
            prev_speaker = segment["speaker"]
            continue
        # Infer from words if present
        inferred = prev_speaker
        words = segment.get("words")
        if isinstance(words, list):
            for w in words:
                if isinstance(w, dict) and w.get("speaker"):
                    inferred = w["speaker"]
                    break
        segment["speaker"] = inferred
        prev_speaker = inferred


def validate_transcript_file(file_path: str) -> bool:
    """
    Validate that a transcript file exists and is in the correct format.

    Uses the same loading path as the pipeline (load_segments) so we validate
    the exact structure the pipeline will use. That way WhisperX-style
    segments with only word-level speaker are normalized by the loader
    before validation, and we avoid requiring raw files to have segment-level
    "speaker" when the loader would fill it from words.

    Args:
        file_path: Path to the transcript file

    Returns:
        True if valid, raises ValueError if invalid

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file format is invalid
    """
    if not file_path:
        raise ValueError("Transcript file path cannot be empty")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Transcript file not found: {file_path}")

    if not file_path.endswith(".json"):
        raise ValueError(
            f"Transcript file must be JSON format, got: {Path(file_path).suffix}"
        )

    try:
        # Use same loader as pipeline so we validate the same structure we run on.
        # Loader fills segment-level "speaker" from words for WhisperX-style files.
        from transcriptx.io.transcript_loader import load_segments

        segments = load_segments(file_path)
        if not segments:
            log_warning("VALIDATION", "Transcript file contains no segments")

        for i, segment in enumerate(segments):
            validate_segment(segment, i)

        return True

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in transcript file: {e}")
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Error validating transcript file: {e}")


def validate_segment(segment: dict[str, Any], index: int) -> bool:
    """
    Validate a single transcript segment.

    Args:
        segment: Segment dictionary
        index: Segment index for error reporting

    Returns:
        True if valid, raises ValueError if invalid
    """
    if not isinstance(segment, dict):
        raise ValueError(f"Segment {index} must be a dictionary")

    required_fields = ["text", "speaker"]
    for field in required_fields:
        if field not in segment:
            raise ValueError(f"Segment {index} missing required field: {field}")

    # Validate text
    if not isinstance(segment["text"], str):
        raise ValueError(f"Segment {index} 'text' must be a string")

    if not segment["text"].strip():
        log_warning("VALIDATION", f"Segment {index} has empty text")

    # Validate speaker
    if not isinstance(segment["speaker"], str):
        raise ValueError(f"Segment {index} 'speaker' must be a string")

    # Validate timestamps if present
    if "start" in segment:
        if not isinstance(segment["start"], (int, float)):
            raise ValueError(f"Segment {index} 'start' must be a number")
        if segment["start"] < 0:
            raise ValueError(f"Segment {index} 'start' cannot be negative")

    if "end" in segment:
        if not isinstance(segment["end"], (int, float)):
            raise ValueError(f"Segment {index} 'end' must be a number")
        if segment["end"] < 0:
            raise ValueError(f"Segment {index} 'end' cannot be negative")

    # Validate start < end if both present
    if "start" in segment and "end" in segment:
        if segment["start"] >= segment["end"]:
            raise ValueError(f"Segment {index} 'start' must be less than 'end'")

    return True


def validate_audio_file(file_path: str) -> bool:
    """
    Validate that an audio file exists and is in a supported format.

    Args:
        file_path: Path to the audio file

    Returns:
        True if valid, raises ValueError if invalid
    """
    if not file_path:
        raise ValueError("Audio file path cannot be empty")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    # Check file extension
    supported_formats = [".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac"]
    file_ext = Path(file_path).suffix.lower()

    if file_ext not in supported_formats:
        raise ValueError(
            f"Unsupported audio format: {file_ext}. Supported: {', '.join(supported_formats)}"
        )

    # Check file size (basic validation)
    file_size = os.path.getsize(file_path)
    if file_size == 0:
        raise ValueError("Audio file is empty")

    if file_size < 1024:  # Less than 1KB
        log_warning(
            "VALIDATION",
            f"Audio file is very small ({file_size} bytes), may be corrupted",
        )

    return True


def validate_output_directory(dir_path: str, create_if_missing: bool = True) -> bool:
    """
    Validate and optionally create an output directory.

    Args:
        dir_path: Path to the output directory
        create_if_missing: Whether to create directory if it doesn't exist

    Returns:
        True if valid, raises ValueError if invalid
    """
    if not dir_path:
        raise ValueError("Output directory path cannot be empty")

    if os.path.exists(dir_path):
        if not os.path.isdir(dir_path):
            raise ValueError(f"Output path exists but is not a directory: {dir_path}")

        # Check write permissions
        if not os.access(dir_path, os.W_OK):
            raise ValueError(f"No write permission for output directory: {dir_path}")
    elif create_if_missing:
        try:
            os.makedirs(dir_path, exist_ok=True)
            log_info("VALIDATION", f"Created output directory: {dir_path}")
        except OSError as e:
            raise ValueError(f"Cannot create output directory {dir_path}: {e}")
    else:
        raise ValueError(f"Output directory does not exist: {dir_path}")

    return True


def validate_speaker_map(speaker_map: dict[str, str]) -> bool:
    """
    Validate a speaker mapping dictionary.

    Args:
        speaker_map: Speaker ID to name mapping

    Returns:
        True if valid, raises ValueError if invalid
    """
    if not isinstance(speaker_map, dict):
        raise ValueError("Speaker map must be a dictionary")

    for speaker_id, speaker_name in speaker_map.items():
        if not isinstance(speaker_id, str):
            raise ValueError(f"Speaker ID must be string, got {type(speaker_id)}")

        if not isinstance(speaker_name, str):
            raise ValueError(f"Speaker name must be string, got {type(speaker_name)}")

        if not speaker_name.strip():
            raise ValueError(f"Speaker name cannot be empty for ID: {speaker_id}")

    return True


def validate_analysis_modules(modules: list[str], available_modules: list[str]) -> bool:
    """
    Validate that requested analysis modules are available.

    Args:
        modules: List of requested module names
        available_modules: List of available module names

    Returns:
        True if valid, raises ValueError if invalid
    """
    if not isinstance(modules, list):
        raise ValueError("Modules must be a list")

    if not modules:
        raise ValueError("At least one analysis module must be specified")

    invalid_modules = [m for m in modules if m not in available_modules]
    if invalid_modules:
        raise ValueError(
            f"Invalid analysis modules: {invalid_modules}. Available: {available_modules}"
        )

    return True


def validate_configuration(config: dict[str, Any]) -> bool:
    """
    Validate configuration dictionary.

    Args:
        config: Configuration dictionary

    Returns:
        True if valid, raises ValueError if invalid
    """
    if not isinstance(config, dict):
        raise ValueError("Configuration must be a dictionary")

    # Validate required top-level keys
    required_sections = ["analysis", "transcription", "output", "logging"]
    for section in required_sections:
        if section not in config:
            raise ValueError(f"Configuration missing required section: {section}")

        if not isinstance(config[section], dict):
            raise ValueError(f"Configuration section '{section}' must be a dictionary")

    # Validate analysis configuration
    analysis = config.get("analysis", {})
    if "sentiment_window_size" in analysis:
        if (
            not isinstance(analysis["sentiment_window_size"], int)
            or analysis["sentiment_window_size"] <= 0
        ):
            raise ValueError("sentiment_window_size must be a positive integer")

    if "emotion_min_confidence" in analysis:
        if not isinstance(analysis["emotion_min_confidence"], (int, float)):
            raise ValueError("emotion_min_confidence must be a number")
        if not 0 <= analysis["emotion_min_confidence"] <= 1:
            raise ValueError("emotion_min_confidence must be between 0 and 1")

    return True


def validate_file_path(
    file_path: str, must_exist: bool = True, file_type: str = "file"
) -> bool:
    """
    Generic file path validation.

    Args:
        file_path: Path to validate
        must_exist: Whether the file must exist
        file_type: Type of file for error messages

    Returns:
        True if valid, raises ValueError if invalid
    """
    if not file_path:
        raise ValueError(f"{file_type.capitalize()} path cannot be empty")

    if not isinstance(file_path, str):
        raise ValueError(f"{file_type.capitalize()} path must be a string")

    if must_exist and not os.path.exists(file_path):
        raise FileNotFoundError(f"{file_type.capitalize()} not found: {file_path}")

    return True


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename for safe file system operations.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    if not filename:
        return "unnamed"

    # Replace problematic characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, "_")

    # Remove leading/trailing spaces and dots
    filename = filename.strip(" .")

    # Ensure it's not empty after sanitization
    if not filename:
        return "unnamed"

    return filename


def validate_and_sanitize_inputs(
    transcript_path: str | None = None,
    audio_path: str | None = None,
    output_dir: str | None = None,
    modules: list[str] | None = None,
    speaker_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Comprehensive validation and sanitization of all inputs.

    Args:
        transcript_path: Path to transcript file
        audio_path: Path to audio file
        output_dir: Output directory path
        modules: List of analysis modules
        speaker_map: Speaker mapping dictionary

    Returns:
        Dictionary of validated and sanitized inputs

    Raises:
        ValueError: If any input is invalid
    """
    validated_inputs = {}

    # Validate transcript file
    if not transcript_path:
        transcript_path = DIARISED_TRANSCRIPTS_DIR
    if transcript_path:
        validate_transcript_file(transcript_path)
        validated_inputs["transcript_path"] = transcript_path

    # Validate audio file
    if not audio_path:
        audio_path = RECORDINGS_DIR
    if audio_path:
        validate_audio_file(audio_path)
        validated_inputs["audio_path"] = audio_path

    # Validate output directory
    if not output_dir:
        output_dir = OUTPUTS_DIR
    if output_dir:
        validate_output_directory(output_dir, create_if_missing=True)
        validated_inputs["output_dir"] = output_dir

    # Validate speaker map
    if speaker_map:
        validate_speaker_map(speaker_map)
        validated_inputs["speaker_map"] = speaker_map

    # Validate modules (if available_modules provided)
    if modules:
        # Note: available_modules would need to be passed or imported
        # For now, just validate basic structure
        if not isinstance(modules, list):
            raise ValueError("Modules must be a list")
        validated_inputs["modules"] = modules

    return validated_inputs
