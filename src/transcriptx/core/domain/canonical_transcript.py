"""
Canonical transcript domain object and capability detection.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

CANONICAL_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class TranscriptCapabilities:
    """Capabilities detected from transcript segments."""

    has_segments: bool
    has_segment_timestamps: bool
    has_speaker_labels: bool
    has_word_timestamps: bool
    has_word_speakers: bool

    @classmethod
    def from_segments(cls, segments: List[Dict[str, Any]]) -> "TranscriptCapabilities":
        has_segments = len(segments) > 0
        has_segment_timestamps = (
            all("start" in seg and "end" in seg for seg in segments)
            if segments
            else False
        )
        has_speaker_labels = any("speaker" in seg for seg in segments)
        has_word_timestamps = any(
            "words" in seg
            and isinstance(seg.get("words"), list)
            and any("start" in word and "end" in word for word in seg.get("words", []))
            for seg in segments
        )
        has_word_speakers = any(
            "words" in seg
            and isinstance(seg.get("words"), list)
            and any("speaker" in word for word in seg.get("words", []))
            for seg in segments
        )
        return cls(
            has_segments=has_segments,
            has_segment_timestamps=has_segment_timestamps,
            has_speaker_labels=has_speaker_labels,
            has_word_timestamps=has_word_timestamps,
            has_word_speakers=has_word_speakers,
        )


def compute_transcript_content_hash(segments: List[Dict[str, Any]]) -> str:
    """
    Compute a deterministic content hash for a transcript.

    Uses a stable JSON representation of segments to produce a SHA-256 hash.
    """
    payload = json.dumps(
        segments, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


@dataclass(frozen=True)
class CanonicalTranscript:
    """Immutable transcript representation with canonical content hash."""

    content_hash: str
    segments: List[Dict[str, Any]]
    capabilities: TranscriptCapabilities
    schema_version: str = CANONICAL_SCHEMA_VERSION
    speaker_identity_hints: Optional[Dict[str, Any]] = None

    @classmethod
    def from_segments(
        cls,
        segments: List[Dict[str, Any]],
        speaker_identity_hints: Optional[Dict[str, Any]] = None,
    ) -> "CanonicalTranscript":
        content_hash = compute_transcript_content_hash(segments)
        capabilities = TranscriptCapabilities.from_segments(segments)
        return cls(
            content_hash=content_hash,
            segments=segments,
            capabilities=capabilities,
            speaker_identity_hints=speaker_identity_hints,
        )
