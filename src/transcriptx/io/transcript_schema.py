"""
Standardized transcript JSON schema for TranscriptX.

This module defines the canonical transcript JSON format with versioning,
source metadata, and validation functions.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib

from transcriptx.core.utils.logger import get_logger

logger = get_logger()

# Current schema version
SCHEMA_VERSION = "1.0"


@dataclass
class SourceInfo:
    """Source metadata for a transcript."""

    type: str  # "vtt", "whisperx", "manual"
    original_path: str
    imported_at: str  # ISO 8601 timestamp
    file_hash: Optional[str] = None
    file_mtime: Optional[float] = None


@dataclass
class TranscriptMetadata:
    """Metadata about the transcript."""

    duration_seconds: float
    segment_count: int
    speaker_count: int


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return f"sha256:{sha256_hash.hexdigest()}"


def validate_schema_version(data: dict) -> bool:
    """
    Check if transcript data matches a supported schema version.

    Args:
        data: Transcript data dictionary

    Returns:
        True if schema version is supported

    Raises:
        ValueError: If schema version is missing or unsupported
    """
    if "schema_version" not in data:
        # Legacy format - assume compatible
        logger.warning("Transcript missing schema_version, assuming legacy format")
        return True

    version = data["schema_version"]
    if version == "1.0":
        return True

    raise ValueError(f"Unsupported schema version: {version}. Supported: 1.0")


def create_transcript_document(
    segments: List[Dict[str, Any]],
    source_info: SourceInfo,
    metadata: Optional[TranscriptMetadata] = None,
) -> Dict[str, Any]:
    """
    Build a standardized transcript document.

    Args:
        segments: List of segment dictionaries
        source_info: Source metadata
        metadata: Optional transcript metadata (will be computed if not provided)

    Returns:
        Standardized transcript document
    """
    # Compute metadata if not provided
    if metadata is None:
        duration = max(seg.get("end", 0) for seg in segments) if segments else 0.0
        segment_count = len(segments)
        speaker_ids = set(seg.get("speaker") for seg in segments if seg.get("speaker"))
        speaker_count = len(speaker_ids)
        metadata = TranscriptMetadata(
            duration_seconds=duration,
            segment_count=segment_count,
            speaker_count=speaker_count,
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "type": source_info.type,
            "original_path": source_info.original_path,
            "imported_at": source_info.imported_at,
            "file_hash": source_info.file_hash,
            "file_mtime": source_info.file_mtime,
        },
        "metadata": {
            "duration_seconds": metadata.duration_seconds,
            "segment_count": metadata.segment_count,
            "speaker_count": metadata.speaker_count,
        },
        "segments": segments,
    }


def validate_segment(segment: Dict[str, Any], index: int) -> None:
    """
    Validate a single segment against the schema.

    Args:
        segment: Segment dictionary
        index: Segment index for error reporting

    Raises:
        ValueError: If segment is invalid
    """
    if not isinstance(segment, dict):
        raise ValueError(f"Segment {index} must be a dictionary")

    # Required fields
    required_fields = ["start", "end", "speaker", "text"]
    for field in required_fields:
        if field not in segment:
            raise ValueError(f"Segment {index} missing required field: {field}")

    # Validate types
    if not isinstance(segment["start"], (int, float)):
        raise ValueError(f"Segment {index} 'start' must be a number")
    if not isinstance(segment["end"], (int, float)):
        raise ValueError(f"Segment {index} 'end' must be a number")
    if not isinstance(segment["text"], str):
        raise ValueError(f"Segment {index} 'text' must be a string")
    if segment["speaker"] is not None and not isinstance(segment["speaker"], str):
        raise ValueError(f"Segment {index} 'speaker' must be a string or null")

    # Validate values
    if segment["start"] < 0:
        raise ValueError(f"Segment {index} 'start' cannot be negative")
    if segment["end"] < 0:
        raise ValueError(f"Segment {index} 'end' cannot be negative")
    if segment["start"] >= segment["end"]:
        raise ValueError(f"Segment {index} 'start' must be less than 'end'")
    if not segment["text"].strip():
        logger.warning(f"Segment {index} has empty text")


def validate_transcript_document(data: Dict[str, Any]) -> None:
    """
    Validate a complete transcript document against the schema.

    Args:
        data: Transcript document dictionary

    Raises:
        ValueError: If document is invalid
    """
    if not isinstance(data, dict):
        raise ValueError("Transcript document must be a dictionary")

    # Validate schema version
    validate_schema_version(data)

    # Validate required top-level keys
    required_keys = ["schema_version", "source", "segments"]
    for key in required_keys:
        if key not in data:
            raise ValueError(f"Transcript document missing required key: {key}")

    # Validate source
    source = data["source"]
    if not isinstance(source, dict):
        raise ValueError("'source' must be a dictionary")
    required_source_keys = ["type", "original_path", "imported_at"]
    for key in required_source_keys:
        if key not in source:
            raise ValueError(f"Source missing required key: {key}")

    # Validate segments
    segments = data["segments"]
    if not isinstance(segments, list):
        raise ValueError("'segments' must be a list")

    if len(segments) == 0:
        logger.warning("Transcript document contains no segments")

    # Validate each segment
    for i, segment in enumerate(segments):
        validate_segment(segment, i)
