"""
Canonical intermediate transcript model.

All source adapters produce this model. It is the single contract passed into
TranscriptNormalizer and SpeakerNormalizer before the schema v1.0 artifact is created.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from typing import TypedDict


@dataclass
class IntermediateTurn:
    """One diarised utterance from any source."""

    text: str
    speaker: Optional[str]  # raw label from source; normalised later
    start: Optional[float]  # seconds; None if source omits timestamps
    end: Optional[float]  # seconds; None if source omits end time
    turn_index: int  # 0-based original order
    raw_turn_id: Optional[str] = None  # vendor-assigned segment/turn ID
    raw: Optional[str] = None  # raw source line(s) before any cleaning
    words: Optional[List[Dict[str, Any]]] = None  # word-level data (e.g. WhisperX)


@dataclass
class IntermediateTranscript:
    """Output of a SourceAdapter.parse() call.

    source_metadata is transient ingestion metadata populated by adapters with
    whatever the source provides (title, date, participants, etc.).  It is
    available throughout the parse → normalize transition and is not currently
    persisted into the schema v1.0 artifact.
    """

    source_tool: str  # e.g. "whisperx", "sembly", "vtt", "srt"
    source_format: str  # "json", "html", "txt", "vtt", "srt"
    turns: List[IntermediateTurn]
    source_metadata: Dict[str, Any]
    warnings: List[str]  # non-fatal parse issues; never raises


# ── TranscriptSegment TypedDict ───────────────────────────────────────────────
# Formally captures the schema v1.0 segment dict shape produced by
# SpeakerNormalizer.  Required fields live in the base class; optional fields
# use total=False in the subclass.


class _TranscriptSegmentRequired(TypedDict):
    start: float
    end: float
    speaker: Optional[str]
    text: str


class TranscriptSegment(_TranscriptSegmentRequired, total=False):
    original_cue: Dict[str, Any]
    cue_id: str
    words: List[Dict[str, Any]]
