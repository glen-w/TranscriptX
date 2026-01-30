"""
Shared Event model for TranscriptX.

Placed in core/models to support reuse across modules (interactions, qa_analysis, etc.).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


@dataclass(frozen=True)
class Event:
    """Generic event used across analysis modules."""

    event_id: str
    kind: str
    time_start: float
    time_end: float
    speaker: Optional[str]
    segment_start_idx: Optional[int]
    segment_end_idx: Optional[int]
    severity: float
    score: Optional[float] = None
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    links: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "kind": self.kind,
            "time_start": self.time_start,
            "time_end": self.time_end,
            "speaker": self.speaker,
            "segment_start_idx": self.segment_start_idx,
            "segment_end_idx": self.segment_end_idx,
            "severity": self.severity,
            "score": self.score,
            "evidence": self.evidence,
            "links": self.links,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        return cls(
            event_id=data.get("event_id", ""),
            kind=data.get("kind", ""),
            time_start=float(data.get("time_start", 0.0)),
            time_end=float(data.get("time_end", 0.0)),
            speaker=data.get("speaker"),
            segment_start_idx=data.get("segment_start_idx"),
            segment_end_idx=data.get("segment_end_idx"),
            severity=float(data.get("severity", 0.0)),
            score=data.get("score"),
            evidence=list(data.get("evidence", [])),
            links=list(data.get("links", [])),
        )


def generate_event_id(
    transcript_hash: str,
    kind: str,
    segment_start_idx: Optional[int],
    segment_end_idx: Optional[int],
    time_start: float,
    time_end: float,
    include_time: bool = True,
    time_precision: int = 1,
    hash_len: int = 16,
) -> str:
    """
    Generate deterministic event_id stable across reruns.

    Uses segment indices as primary identity (stable), with optional rounded
    timestamps for disambiguation when needed.
    """
    idx_str = f"{segment_start_idx if segment_start_idx is not None else 'none'}-{segment_end_idx if segment_end_idx is not None else 'none'}"
    if include_time:
        time_str = f"{round(time_start, time_precision)}-{round(time_end, time_precision)}"
        fingerprint = f"{transcript_hash}:{kind}:{idx_str}:{time_str}"
    else:
        fingerprint = f"{transcript_hash}:{kind}:{idx_str}"
    return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:hash_len]


def sort_event_key(event: Event) -> tuple:
    """Deterministic sort key for events."""
    return (
        float(event.time_start),
        event.kind or "",
        event.segment_start_idx if event.segment_start_idx is not None else -1,
        event.segment_end_idx if event.segment_end_idx is not None else -1,
        event.event_id or "",
    )


def sort_events_deterministically(events: Iterable[Event]) -> List[Event]:
    """Return events sorted deterministically for stable snapshots."""
    return sorted(list(events), key=sort_event_key)
