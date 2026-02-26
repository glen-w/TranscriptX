"""Search models for TranscriptX web UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class TranscriptRef:
    session_slug: str
    run_id: str
    transcript_file_id: Optional[int] = None
    transcript_slug: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "session_slug": self.session_slug,
            "run_id": self.run_id,
            "transcript_file_id": self.transcript_file_id,
            "transcript_slug": self.transcript_slug,
        }

    @staticmethod
    def from_dict(payload: Dict[str, Any]) -> TranscriptRef:
        transcript_file_id = payload.get("transcript_file_id")
        if isinstance(transcript_file_id, str) and transcript_file_id.isdigit():
            transcript_file_id = int(transcript_file_id)
        return TranscriptRef(
            session_slug=payload.get("session_slug") or "",
            run_id=payload.get("run_id") or "",
            transcript_file_id=transcript_file_id,
            transcript_slug=payload.get("transcript_slug"),
        )


@dataclass(frozen=True)
class SegmentRef:
    transcript_ref: TranscriptRef
    primary_locator: str
    segment_id: Optional[int] = None
    segment_index: Optional[int] = None
    timecode: Optional[float] = None

    def __post_init__(self) -> None:
        if self.segment_id is None and self.segment_index is None:
            raise ValueError("SegmentRef requires segment_id or segment_index.")
        if self.primary_locator == "db_id":
            if self.segment_id is None:
                raise ValueError(
                    "SegmentRef primary_locator db_id requires segment_id."
                )
        elif self.primary_locator == "index":
            if self.segment_index is None:
                raise ValueError(
                    "SegmentRef primary_locator index requires segment_index."
                )
        else:
            raise ValueError(f"Unknown primary_locator: {self.primary_locator}")

    def to_dict(self) -> Dict[str, object]:
        return {
            "transcript_ref": self.transcript_ref.to_dict(),
            "primary_locator": self.primary_locator,
            "segment_id": self.segment_id,
            "segment_index": self.segment_index,
            "timecode": self.timecode,
        }

    @staticmethod
    def from_dict(payload: Dict[str, Any]) -> SegmentRef:
        transcript_payload = payload.get("transcript_ref") or {}
        if not isinstance(transcript_payload, dict):
            transcript_payload = {}
        segment_id = payload.get("segment_id")
        segment_index = payload.get("segment_index")
        timecode = payload.get("timecode")
        if isinstance(segment_id, str) and segment_id.isdigit():
            segment_id = int(segment_id)
        if isinstance(segment_index, str) and segment_index.isdigit():
            segment_index = int(segment_index)
        if isinstance(timecode, str):
            try:
                timecode = float(timecode)
            except ValueError:
                timecode = None
        return SegmentRef(
            transcript_ref=TranscriptRef.from_dict(transcript_payload),
            primary_locator=payload.get("primary_locator") or "index",
            segment_id=segment_id,
            segment_index=segment_index,
            timecode=timecode if isinstance(timecode, (int, float)) else None,
        )


@dataclass
class SearchResult:
    segment_ref: SegmentRef
    transcript_title: str
    session_slug: str
    run_id: str
    segment_id: Optional[int]
    segment_index: int
    segment_text: str
    match_spans: List[Tuple[int, int]]
    speaker_name: str
    speaker_is_named: bool
    start_time: float
    end_time: float
    context_indices: Optional[Tuple[int, int]] = None

    def __post_init__(self) -> None:
        if self.session_slug != self.segment_ref.transcript_ref.session_slug:
            raise ValueError("SearchResult session_slug does not match SegmentRef.")
        if self.run_id != self.segment_ref.transcript_ref.run_id:
            raise ValueError("SearchResult run_id does not match SegmentRef.")
        if self.segment_index is None:
            raise ValueError("SearchResult requires segment_index.")


@dataclass
class SearchResponse:
    substring_results: List[SearchResult]
    fuzzy_results: List[SearchResult]
    total_found: int
    total_shown: int
    fuzzy_ran: bool
    fuzzy_reason: Optional[str] = None


@dataclass
class NavRequest:
    segment_ref: SegmentRef
    highlight_query: Optional[str] = None


@dataclass
class SearchFilters:
    speaker_keys: List[str] = field(default_factory=list)
    speaker_ids: Optional[List[int]] = None
    speaker_names: Optional[List[str]] = None
    session_slugs: Optional[List[str]] = None
    date_range: Optional[Tuple[object, object]] = None
