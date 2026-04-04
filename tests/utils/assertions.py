"""
Assertion helpers for TranscriptX testing.

This module provides specialized assertion functions for validating
transcript data, speaker maps, output structures, and file operations.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def assert_valid_transcript(transcript: Dict[str, Any], strict: bool = True) -> None:
    """
    Assert that a transcript has valid structure.

    Args:
        transcript: Transcript dictionary to validate
        strict: If True, validates all required fields; if False, only checks structure

    Raises:
        AssertionError: If transcript is invalid

    Note:
        Validates:
        - Has 'segments' key
        - Segments is a list
        - Each segment has required fields (speaker, text)
        - Timestamps are valid (if present)
    """
    assert isinstance(transcript, dict), "Transcript must be a dictionary"
    assert "segments" in transcript, "Transcript must have 'segments' key"
    assert isinstance(transcript["segments"], list), "Segments must be a list"

    if strict:
        for i, segment in enumerate(transcript["segments"]):
            assert isinstance(segment, dict), f"Segment {i} must be a dictionary"
            assert "speaker" in segment, f"Segment {i} must have 'speaker' field"
            assert "text" in segment, f"Segment {i} must have 'text' field"

            # Validate timestamps if present
            if "start" in segment:
                assert isinstance(
                    segment["start"], (int, float)
                ), f"Segment {i} start must be numeric"
            if "end" in segment:
                assert isinstance(
                    segment["end"], (int, float)
                ), f"Segment {i} end must be numeric"
                if "start" in segment:
                    assert (
                        segment["end"] >= segment["start"]
                    ), f"Segment {i} end must be >= start"


def assert_valid_speaker_map(speaker_map: Dict[str, str]) -> None:
    """
    Assert that a speaker map has valid structure.

    Args:
        speaker_map: Speaker map dictionary to validate

    Raises:
        AssertionError: If speaker map is invalid

    Note:
        Validates:
        - Is a dictionary
        - All values are strings
        - No empty values (unless explicitly allowed)
    """
    assert isinstance(speaker_map, dict), "Speaker map must be a dictionary"

    for speaker_id, name in speaker_map.items():
        assert isinstance(
            speaker_id, str
        ), f"Speaker ID must be string, got {type(speaker_id)}"
        assert isinstance(name, str), f"Speaker name must be string, got {type(name)}"
        assert len(name) > 0, f"Speaker name cannot be empty for {speaker_id}"


def assert_valid_output_structure(
    output_structure: Any, required_keys: Optional[List[str]] = None
) -> None:
    """
    Assert that an output structure is valid.

    Args:
        output_structure: Output structure to validate (usually a dataclass or dict)
        required_keys: List of required keys (if None, uses defaults)

    Raises:
        AssertionError: If output structure is invalid

    Note:
        Validates:
        - Is a dictionary or has dict-like attributes
        - Contains required keys (module_dir, data_dir, etc.)
    """
    if required_keys is None:
        required_keys = ["module_dir"]

    # Handle dataclass-like objects
    if hasattr(output_structure, "__dict__"):
        structure_dict = output_structure.__dict__
    elif isinstance(output_structure, dict):
        structure_dict = output_structure
    else:
        raise AssertionError(
            f"Output structure must be dict or have __dict__, got {type(output_structure)}"
        )

    for key in required_keys:
        assert key in structure_dict or hasattr(
            output_structure, key
        ), f"Output structure must have '{key}' field"


def assert_files_exist(file_paths: List[str], all_must_exist: bool = True) -> None:
    """
    Assert that files exist.

    Args:
        file_paths: List of file paths to check
        all_must_exist: If True, all files must exist; if False, at least one must exist

    Raises:
        AssertionError: If file existence requirements are not met
    """
    assert isinstance(file_paths, list), "file_paths must be a list"
    assert len(file_paths) > 0, "file_paths cannot be empty"

    existing_files = [path for path in file_paths if Path(path).exists()]

    if all_must_exist:
        missing_files = [path for path in file_paths if path not in existing_files]
        assert len(missing_files) == 0, f"Missing files: {missing_files}"
    else:
        assert len(existing_files) > 0, f"None of the files exist: {file_paths}"


def assert_json_valid(
    file_path: str, schema: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Assert that a JSON file is valid and optionally matches a schema.

    Args:
        file_path: Path to JSON file
        schema: Optional schema to validate against

    Returns:
        Parsed JSON data

    Raises:
        AssertionError: If JSON is invalid or doesn't match schema
        FileNotFoundError: If file doesn't exist
    """
    assert Path(file_path).exists(), f"JSON file does not exist: {file_path}"

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Invalid JSON in {file_path}: {e}")

    if schema:
        # Basic schema validation (can be enhanced with jsonschema library)
        for key, expected_type in schema.items():
            assert key in data, f"Missing required key '{key}' in JSON"
            assert isinstance(
                data[key], expected_type
            ), f"Key '{key}' must be {expected_type.__name__}, got {type(data[key]).__name__}"

    return data


def assert_transcript_consistency(
    transcript: Dict[str, Any], speaker_map: Dict[str, str]
) -> None:
    """
    Assert consistency between transcript and speaker map.

    Args:
        transcript: Transcript dictionary
        speaker_map: Speaker map dictionary

    Raises:
        AssertionError: If transcript and speaker map are inconsistent

    Note:
        Validates:
        - All speakers in transcript exist in speaker map
        - No orphaned speakers in speaker map (optional check)
    """
    assert_valid_transcript(transcript)
    assert_valid_speaker_map(speaker_map)

    # Get all speakers from transcript
    transcript_speakers = set()
    for segment in transcript.get("segments", []):
        speaker = segment.get("speaker")
        if speaker:
            transcript_speakers.add(speaker)

    # Check all transcript speakers are in map
    missing_speakers = transcript_speakers - set(speaker_map.keys())
    assert (
        len(missing_speakers) == 0
    ), f"Speakers in transcript not found in speaker map: {missing_speakers}"
