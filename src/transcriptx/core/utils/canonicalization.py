"""
Canonicalization utilities for transcript hashing.

This module defines deterministic normalization and hashing for transcript content.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

SCHEMA_VERSION = "transcript_canon_v1"
SENTENCE_SCHEMA_VERSION = "sentence_splitter_v1"
DEFAULT_TIME_DECIMALS = 3


@dataclass(frozen=True)
class CanonicalSegment:
    start: str
    end: str
    speaker_label: str
    text: str
    language: Optional[str] = None


def normalize_text(text: str) -> str:
    """Normalize text for hashing with conservative rules."""
    normalized = text.replace("\r\n", "\n")
    normalized = "\n".join(line.rstrip() for line in normalized.split("\n"))
    normalized = normalized.strip()
    return normalized


def normalize_timestamp(value: float, decimals: int = DEFAULT_TIME_DECIMALS) -> str:
    """Normalize timestamp to a fixed decimal string."""
    return f"{round(float(value), decimals):.{decimals}f}"


def canonicalize_segments(
    segments: Iterable[Dict[str, Any]],
    language: Optional[str] = None,
    decimals: int = DEFAULT_TIME_DECIMALS,
) -> List[CanonicalSegment]:
    """Canonicalize segments into typed structures for stable hashing."""
    canonical: List[CanonicalSegment] = []
    for segment in segments:
        canonical.append(
            CanonicalSegment(
                start=normalize_timestamp(segment.get("start", 0.0), decimals=decimals),
                end=normalize_timestamp(segment.get("end", 0.0), decimals=decimals),
                speaker_label=str(segment.get("speaker", "")),
                text=normalize_text(segment.get("text", "")),
                language=segment.get("language") or language,
            )
        )
    return canonical


def _canonical_segments_to_bytes(canonical_segments: List[CanonicalSegment]) -> bytes:
    payload = [
        {
            "start": seg.start,
            "end": seg.end,
            "speaker_label": seg.speaker_label,
            "text": seg.text,
            "language": seg.language,
        }
        for seg in canonical_segments
    ]
    serialized = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return serialized.encode("utf-8")


def compute_transcript_content_hash(
    segments: Iterable[Dict[str, Any]],
    language: Optional[str] = None,
    decimals: int = DEFAULT_TIME_DECIMALS,
) -> str:
    """Compute the transcript content hash from canonicalized segments."""
    canonical_segments = canonicalize_segments(
        segments, language=language, decimals=decimals
    )
    hash_obj = hashlib.sha256(_canonical_segments_to_bytes(canonical_segments))
    return hash_obj.hexdigest()


def compute_transcript_identity_hash(
    segments: Iterable[Dict[str, Any]],
    decimals: int = DEFAULT_TIME_DECIMALS,
) -> str:
    """
    Compute a stable transcript identity hash based on text + timestamps only.

    This intentionally ignores speaker fields, words arrays, and derived metadata.
    """
    payload = [
        {
            "start": normalize_timestamp(seg.get("start", 0.0), decimals=decimals),
            "end": normalize_timestamp(seg.get("end", 0.0), decimals=decimals),
            "text": normalize_text(str(seg.get("text", ""))),
        }
        for seg in segments
    ]
    serialized = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return f"sha256:{hashlib.sha256(serialized.encode('utf-8')).hexdigest()}"


def compute_source_hash(file_path: str) -> str:
    """Compute SHA256 hash of a source file for forensic traceability."""
    hash_obj = hashlib.sha256()
    with open(file_path, "rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            hash_obj.update(chunk)
    return hash_obj.hexdigest()
