"""
Standardized transcript JSON schema for TranscriptX.

This module defines the canonical transcript JSON format with versioning,
source metadata, and validation functions.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from transcriptx.core.utils.logger import get_logger

logger = get_logger()

# Current schema version
SCHEMA_VERSION = "1.0"

# Permitted source.type values (one per adapter source_id, plus "manual").
# This list grows as new adapters are introduced.  Validation is permissive:
# unknown values are warned about, not rejected, so third-party adapters
# registered outside the core still work.
PERMITTED_SOURCE_TYPES = frozenset(
    {
        "vtt",
        "srt",
        "whisperx",
        "sembly",
        "otter",
        "fireflies",
        "rev",
        "zoom",
        "generic_text",
        "manual",
    }
)


@dataclass
class SourceInfo:
    """Source metadata for a transcript.

    ``type`` is the adapter ``source_id`` string written into
    ``source.type`` in the JSON artifact.  Permitted values:
    "vtt", "srt", "whisperx", "sembly", "otter", "fireflies", "rev",
    "zoom", "generic_text", "manual".  New adapters extend this list in
    ``PERMITTED_SOURCE_TYPES`` when introduced.
    """

    type: str
    original_path: str
    imported_at: str  # ISO 8601 timestamp with timezone
    file_hash: Optional[str] = None
    file_mtime: Optional[float] = None


@dataclass
class TranscriptMetadata:
    """Metadata about the transcript."""

    duration_seconds: float
    segment_count: int
    speaker_count: int


# ── Hash utilities ─────────────────────────────────────────────────────────────


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA-256 hash by reading *file_path* from disk."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return f"sha256:{sha256_hash.hexdigest()}"


def compute_content_hash(content: bytes) -> str:
    """Compute SHA-256 hash of already-read *content* bytes.

    Use this inside ``import_transcript()`` to avoid a second disk read when
    the file bytes are already in memory.
    """
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


# ── Validation ─────────────────────────────────────────────────────────────────


def validate_schema_version(data: dict) -> bool:
    """Check if transcript data matches a supported schema version.

    Legacy files without ``schema_version`` are tolerated with a warning
    (backward compatibility).  This function is intentionally permissive;
    ``validate_transcript_document()`` is the strict full-document check.

    Returns:
        True if schema version is supported or absent (legacy).

    Raises:
        ValueError: If schema_version is present but unsupported.
    """
    if "schema_version" not in data:
        logger.warning("Transcript missing schema_version; assuming legacy format")
        return True

    version = data["schema_version"]
    if version == "1.0":
        return True

    raise ValueError(f"Unsupported schema version: {version}. Supported: 1.0")


def create_transcript_document(
    segments: Sequence[Dict[str, Any]],
    source_info: SourceInfo,
    metadata: Optional[TranscriptMetadata] = None,
) -> Dict[str, Any]:
    """Build a standardised transcript document.

    Args:
        segments: Sequence of segment dicts conforming to schema v1.0.
        source_info: Source metadata (adapter id, path, timestamps, hash).
        metadata: Optional summary stats; computed from *segments* when absent.

    Returns:
        Standardised transcript document dict.
    """
    if metadata is None:
        duration = max((seg.get("end", 0) for seg in segments), default=0.0)
        segment_count = len(segments)
        speaker_ids = {seg.get("speaker") for seg in segments if seg.get("speaker")}
        speaker_count = len(speaker_ids)
        metadata = TranscriptMetadata(
            duration_seconds=duration,
            segment_count=segment_count,
            speaker_count=speaker_count,
        )

    if source_info.type not in PERMITTED_SOURCE_TYPES:
        logger.warning(
            f"source.type={source_info.type!r} is not in PERMITTED_SOURCE_TYPES. "
            "Add it to transcript_schema.PERMITTED_SOURCE_TYPES when introducing a new adapter."
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
        "segments": list(segments),
    }


def validate_segment(segment: Dict[str, Any], index: int) -> None:
    """Validate a single segment against the schema.

    Raises:
        ValueError: If segment is invalid.
    """
    if not isinstance(segment, dict):
        raise ValueError(f"Segment {index} must be a dictionary")

    required_fields = ["start", "end", "speaker", "text"]
    for field in required_fields:
        if field not in segment:
            raise ValueError(f"Segment {index} missing required field: {field}")

    if not isinstance(segment["start"], (int, float)):
        raise ValueError(f"Segment {index} 'start' must be a number")
    if not isinstance(segment["end"], (int, float)):
        raise ValueError(f"Segment {index} 'end' must be a number")
    if not isinstance(segment["text"], str):
        raise ValueError(f"Segment {index} 'text' must be a string")
    if segment["speaker"] is not None and not isinstance(segment["speaker"], str):
        raise ValueError(f"Segment {index} 'speaker' must be a string or null")

    if segment["start"] < 0:
        raise ValueError(f"Segment {index} 'start' cannot be negative")
    if segment["end"] < 0:
        raise ValueError(f"Segment {index} 'end' cannot be negative")
    if segment["start"] >= segment["end"]:
        raise ValueError(f"Segment {index} 'start' must be less than 'end'")
    if not segment["text"].strip():
        logger.warning(f"Segment {index} has empty text")


def validate_transcript_document(data: Dict[str, Any]) -> None:
    """Validate a complete transcript document against the schema.

    Legacy documents without ``schema_version`` are tolerated (a warning is
    logged by ``validate_schema_version``).  The presence of ``source`` and
    ``segments`` is always required.

    Raises:
        ValueError: If document structure is invalid.
    """
    if not isinstance(data, dict):
        raise ValueError("Transcript document must be a dictionary")

    # schema_version is optional for legacy docs; validate_schema_version handles it
    validate_schema_version(data)

    # source and segments are always required
    for key in ("source", "segments"):
        if key not in data:
            raise ValueError(f"Transcript document missing required key: {key!r}")

    source = data["source"]
    if not isinstance(source, dict):
        raise ValueError("'source' must be a dictionary")
    for key in ("type", "original_path", "imported_at"):
        if key not in source:
            raise ValueError(f"Source missing required key: {key!r}")

    segments = data["segments"]
    if not isinstance(segments, list):
        raise ValueError("'segments' must be a list")

    if len(segments) == 0:
        logger.warning("Transcript document contains no segments")

    for i, segment in enumerate(segments):
        validate_segment(segment, i)
