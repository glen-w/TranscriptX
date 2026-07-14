"""Build canonical transcript documents from adapter output."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from transcriptx.io.intermediate_transcript import TranscriptSegment
from transcriptx.io.transcript_schema import (
    SourceInfo,
    compute_content_hash,
    compute_metadata_from_segments,
    create_transcript_document,
    validate_transcript_document,
)


@dataclass(frozen=True)
class CanonicalBuildInput:
    source_type: str
    source_path: Path
    imported_at: str
    segments: Sequence[TranscriptSegment]
    content: bytes
    source_original_path: str | None = None


def build_canonical_document(input_data: CanonicalBuildInput) -> dict:
    metadata = compute_metadata_from_segments(input_data.segments)
    source_info = SourceInfo(
        type=input_data.source_type,
        original_path=input_data.source_original_path
        or str(input_data.source_path.resolve()),
        imported_at=input_data.imported_at,
        file_hash=compute_content_hash(input_data.content),
        file_mtime=os.path.getmtime(input_data.source_path),
    )
    document = create_transcript_document(input_data.segments, source_info, metadata)
    validate_transcript_document(document)
    return document
