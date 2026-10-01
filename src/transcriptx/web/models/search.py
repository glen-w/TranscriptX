"""Search models for TranscriptX web UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from transcriptx.core.models.navigation import SegmentRef, TranscriptRef

__all__ = ["SegmentRef", "TranscriptRef", "SearchResult", "SearchResponse", "NavRequest", "SearchFilters"]


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
    context_before: Optional[str] = None
    context_after: Optional[str] = None

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
