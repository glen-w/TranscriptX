"""Canonical transcript semantic validation.

Provides a lightweight validator for canonical transcript JSON artifacts,
distinct from managed-transcript validation (which also checks sidecars
and archival/original linkage).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from transcriptx.io.transcript_schema import validate_transcript_document
from transcriptx.core.observability.perf import (
    observe_transcript_path,
    record_file_read,
)


class CanonicalTranscriptCategory(str, Enum):
    ok = "ok"
    not_found = "not_found"
    bad_extension = "bad_extension"
    parse_error = "parse_error"
    schema_error = "schema_error"


@dataclass(frozen=True)
class CanonicalValidationResult:
    ok: bool
    category: CanonicalTranscriptCategory
    message: str


def validate_canonical_transcript(path: str | Path) -> CanonicalValidationResult:
    """Validate that a file is a well-formed canonical transcript JSON artifact.

    This checks only the transcript document itself (schema_version, source,
    segments, etc.) and does NOT validate managed sidecars or archival linkage.
    """
    transcript = Path(path)
    if not transcript.exists():
        return CanonicalValidationResult(
            ok=False,
            category=CanonicalTranscriptCategory.not_found,
            message=f"Transcript not found: {transcript}",
        )
    if transcript.suffix.lower() != ".json":
        return CanonicalValidationResult(
            ok=False,
            category=CanonicalTranscriptCategory.bad_extension,
            message=f"Transcript must be .json, got: {transcript.suffix!r}",
        )
    try:
        import json

        observe_transcript_path(transcript)
        record_file_read(
            transcript,
            section="validate_canonical_transcript",
            purpose="transcript_validation",
        )
        with transcript.open("r", encoding="utf-8") as handle:
            doc: Any = json.load(handle)
    except Exception as exc:
        return CanonicalValidationResult(
            ok=False,
            category=CanonicalTranscriptCategory.parse_error,
            message=f"Failed to parse transcript JSON: {exc}",
        )

    try:
        validate_transcript_document(doc, label=str(transcript))
    except Exception as exc:
        return CanonicalValidationResult(
            ok=False,
            category=CanonicalTranscriptCategory.schema_error,
            message=f"Transcript schema validation failed: {exc}",
        )

    return CanonicalValidationResult(
        ok=True,
        category=CanonicalTranscriptCategory.ok,
        message="Canonical transcript is valid",
    )


def is_canonical_transcript(path: str | Path) -> bool:
    """Convenience helper returning only the ok flag."""
    return validate_canonical_transcript(path).ok
