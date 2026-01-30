"""
Centralized transcript importer interface.

This module provides a single entrypoint for importing transcripts from various
formats (VTT, JSON) and creating standardized JSON artifacts.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import DIARISED_TRANSCRIPTS_DIR
from transcriptx.io.segment_coalescer import CoalesceConfig, coalesce_segments
from transcriptx.io.speaker_normalizer import normalize_speakers
from transcriptx.io.transcript_schema import (
    SourceInfo,
    TranscriptMetadata,
    compute_file_hash,
    create_transcript_document,
    validate_transcript_document,
)
from transcriptx.io.vtt_parser import parse_vtt_file
from transcriptx.io.srt_parser import parse_srt_file

logger = get_logger()


def detect_transcript_format(path: Path) -> str:
    """
    Detect the format of a transcript file.

    Args:
        path: Path to transcript file

    Returns:
        Format string: "vtt" or "json"

    Raises:
        ValueError: If format cannot be determined
    """
    ext = path.suffix.lower()
    if ext == ".vtt":
        return "vtt"
    elif ext == ".json":
        return "json"
    elif ext == ".srt":
        return "srt"
    else:
        raise ValueError(
            f"Unsupported transcript format: {ext}. Supported: .vtt, .json, .srt"
        )


def ensure_json_artifact(path: Path) -> Path:
    """
    Ensure a JSON artifact exists for the given transcript path.

    If path is VTT, import and return JSON path.
    If path is JSON, return as-is.

    Args:
        path: Path to transcript file (VTT or JSON)

    Returns:
        Path to JSON artifact
    """
    format_type = detect_transcript_format(path)

    if format_type == "json":
        return path

    # VTT - import it
    json_path = import_transcript(path)
    return json_path


def import_transcript(
    source_path: str | Path,
    output_dir: Optional[str | Path] = None,
    coalesce_config: Optional[CoalesceConfig] = None,
    overwrite: bool = False,
) -> Path:
    """
    Import a transcript file (VTT or JSON) and create standardized JSON artifact.

    Flow:
    1. Detect file format (.vtt or .json)
    2. If .vtt: Parse → Normalize speakers → (Optional) Coalesce → Create JSON document
    3. If .json: Validate schema → (Optional) Migrate/upgrade → Return path
    4. Compute file hash and metadata
    5. Save standardized JSON to output directory
    6. Return path to JSON artifact

    Args:
        source_path: Path to source file (.vtt or .json)
        output_dir: Directory to save JSON artifact (default: DIARISED_TRANSCRIPTS_DIR)
        coalesce_config: Optional segment coalescing configuration
        overwrite: Whether to overwrite existing JSON file

    Returns:
        Path to created JSON artifact

    Raises:
        ValueError: If file format is unsupported or invalid
        FileNotFoundError: If source file doesn't exist
    """
    source_path = Path(source_path)

    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    # Detect format
    format_type = detect_transcript_format(source_path)
    logger.info(f"Importing {format_type.upper()} transcript: {source_path}")

    # Set output directory
    if output_dir is None:
        output_dir = Path(DIARISED_TRANSCRIPTS_DIR)
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine output JSON path
    json_filename = source_path.stem + ".json"
    json_path = output_dir / json_filename

    # Check if already exists
    if json_path.exists() and not overwrite:
        logger.info(f"JSON artifact already exists: {json_path}")
        return json_path

    # Process based on format
    if format_type == "vtt":
        # Parse VTT
        cues = parse_vtt_file(source_path)
        if not cues:
            raise ValueError(f"No cues found in VTT file: {source_path}")

        # Normalize speakers
        segments = normalize_speakers(cues)

        # Optional coalescing
        if coalesce_config and coalesce_config.enabled:
            segments = coalesce_segments(segments, coalesce_config)

        # Compute metadata
        duration = max(seg.get("end", 0) for seg in segments) if segments else 0.0
        speaker_ids = set(seg.get("speaker") for seg in segments if seg.get("speaker"))
        metadata = TranscriptMetadata(
            duration_seconds=duration,
            segment_count=len(segments),
            speaker_count=len(speaker_ids),
        )

        # Create source info
        file_hash = compute_file_hash(source_path)
        file_mtime = os.path.getmtime(source_path)
        source_info = SourceInfo(
            type="vtt",
            original_path=str(source_path.resolve()),
            imported_at=datetime.utcnow().isoformat() + "Z",
            file_hash=file_hash,
            file_mtime=file_mtime,
        )

        # Create standardized document
        document = create_transcript_document(segments, source_info, metadata)

    elif format_type == "srt":
        cues = parse_srt_file(source_path)
        if not cues:
            raise ValueError(f"No cues found in SRT file: {source_path}")

        segments = normalize_speakers(cues)

        if coalesce_config and coalesce_config.enabled:
            segments = coalesce_segments(segments, coalesce_config)

        duration = max(seg.get("end", 0) for seg in segments) if segments else 0.0
        speaker_ids = set(seg.get("speaker") for seg in segments if seg.get("speaker"))
        metadata = TranscriptMetadata(
            duration_seconds=duration,
            segment_count=len(segments),
            speaker_count=len(speaker_ids),
        )

        file_hash = compute_file_hash(source_path)
        file_mtime = os.path.getmtime(source_path)
        source_info = SourceInfo(
            type="srt",
            original_path=str(source_path.resolve()),
            imported_at=datetime.utcnow().isoformat() + "Z",
            file_hash=file_hash,
            file_mtime=file_mtime,
        )

        document = create_transcript_document(segments, source_info, metadata)

    elif format_type == "json":
        # Load existing JSON
        with open(source_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Validate schema
        try:
            validate_transcript_document(data)
        except ValueError as e:
            logger.warning(
                f"JSON file validation failed: {e}. Attempting to upgrade..."
            )
            # For now, just copy as-is if validation fails
            # TODO: Implement schema migration/upgrade logic

        # If already standardized, use as-is
        if "schema_version" in data and "source" in data:
            document = data
            # Update source info if needed
            if document["source"]["type"] != "json":
                # Keep original source info
                pass
        else:
            # Legacy format - wrap in standardized schema
            segments = data.get("segments", data if isinstance(data, list) else [])
            duration = max(seg.get("end", 0) for seg in segments) if segments else 0.0
            speaker_ids = set(
                seg.get("speaker") for seg in segments if seg.get("speaker")
            )
            metadata = TranscriptMetadata(
                duration_seconds=duration,
                segment_count=len(segments),
                speaker_count=len(speaker_ids),
            )

            file_hash = compute_file_hash(source_path)
            file_mtime = os.path.getmtime(source_path)
            source_info = SourceInfo(
                type="whisperx",  # Assume legacy JSON is from WhisperX
                original_path=str(source_path.resolve()),
                imported_at=datetime.utcnow().isoformat() + "Z",
                file_hash=file_hash,
                file_mtime=file_mtime,
            )

            document = create_transcript_document(segments, source_info, metadata)

    else:
        raise ValueError(f"Unsupported format: {format_type}")

    # Validate document before saving
    validate_transcript_document(document)

    # Save JSON artifact
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(document, f, indent=2, ensure_ascii=False)

    logger.info(f"Created JSON artifact: {json_path}")
    logger.info(f"  Segments: {document['metadata']['segment_count']}")
    logger.info(f"  Duration: {document['metadata']['duration_seconds']:.2f}s")
    logger.info(f"  Speakers: {document['metadata']['speaker_count']}")

    return json_path
