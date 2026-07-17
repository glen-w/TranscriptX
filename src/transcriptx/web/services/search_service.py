# mypy: ignore-missing-imports
"""Search service for TranscriptX web UI.

File-backed, in-process index (`@st.cache_data`) with substring / multi-term AND
matching, optional fuzzy fallback (rapidfuzz), and a hard result cap of 200.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Protocol, Tuple
import re

import streamlit as st

from transcriptx.core.utils.logger import get_logger
from transcriptx.web.models.search import (
    SearchFilters,
    SearchResponse,
    SearchResult,
    SegmentRef,
    TranscriptRef,
)
from transcriptx.web.cache_helpers import cached_list_available_sessions
from transcriptx.web.services.file_service import FileService
from transcriptx.web.utils import resolve_speaker_names_from_sidecars

logger = get_logger()


def _normalize(text: str) -> str:
    return text.lower()


def _tokenize(query: str) -> List[str]:
    return [t for t in re.split(r"\W+", _normalize(query)) if len(t) >= 3]


def _find_spans(text: str, query: str) -> List[Tuple[int, int]]:
    if not query:
        return []
    spans: List[Tuple[int, int]] = []
    lower_text = _normalize(text)
    lower_query = _normalize(query)
    start = 0
    while True:
        idx = lower_text.find(lower_query, start)
        if idx == -1:
            break
        spans.append((idx, idx + len(lower_query)))
        start = idx + len(lower_query)
    return spans


def _is_word_boundary_match(text: str, query: str) -> bool:
    if not query:
        return False
    lower_text = _normalize(text)
    lower_query = _normalize(query)
    escaped = re.escape(lower_query)
    pattern = re.compile(rf"(?<!\w){escaped}(?!\w)")
    return bool(pattern.search(lower_text))


def _is_phrase_match(text: str, query: str) -> bool:
    return _normalize(query) in _normalize(text)


def _session_slug_from_name(session_name: str) -> str:
    return session_name.split("/", 1)[0]


def _session_matches_filters(
    session_name: str, filters: Optional[SearchFilters]
) -> bool:
    if not filters or not filters.session_slugs:
        return True
    slug = _session_slug_from_name(session_name)
    return slug in set(filters.session_slugs)


def _segment_matches_speaker_filters(
    segment: Dict[str, object], filters: Optional[SearchFilters]
) -> bool:
    if not filters or not filters.speaker_keys:
        return True
    speaker = segment.get("speaker_display") or segment.get("speaker") or ""
    speaker_str = str(speaker).strip()
    return speaker_str in set(filters.speaker_keys)


def _match_segment_text(
    text: str, query: str
) -> Optional[Tuple[List[Tuple[int, int]], bool]]:
    """Return (spans, is_phrase_match) if the segment matches, else None.

    Phrase / contiguous substring is preferred. When that fails and the query
    has 2+ tokens (len >= 3), accept when every token appears (AND).
    """
    if _is_phrase_match(text, query):
        return _find_spans(text, query), True
    tokens = _tokenize(query)
    if len(tokens) < 2:
        return None
    lower = _normalize(text)
    if not all(token in lower for token in tokens):
        return None
    spans: List[Tuple[int, int]] = []
    for token in tokens:
        spans.extend(_find_spans(text, token))
    spans.sort(key=lambda item: item[0])
    return spans, False


def _neighbor_context(
    segments: List[Dict[str, object]], idx: int
) -> Tuple[Optional[str], Optional[str], Tuple[int, int]]:
    before: Optional[str] = None
    after: Optional[str] = None
    if idx > 0:
        prev = segments[idx - 1].get("text", "")
        if isinstance(prev, str) and prev.strip():
            before = prev
    if idx + 1 < len(segments):
        nxt = segments[idx + 1].get("text", "")
        if isinstance(nxt, str) and nxt.strip():
            after = nxt
    context_indices = (max(0, idx - 1), idx + 1)
    return before, after, context_indices


def _build_search_result(
    *,
    session_name: str,
    index: _TranscriptIndex,
    segments: List[Dict[str, object]],
    idx: int,
    segment: Dict[str, object],
    text: str,
    match_spans: List[Tuple[int, int]],
) -> SearchResult:
    speaker_name = segment.get("speaker_display") or segment.get("speaker") or "Unknown"
    speaker_name = str(speaker_name)
    session_slug, run_id = session_name.split("/", 1)
    before, after, context_indices = _neighbor_context(segments, idx)
    return SearchResult(
        segment_ref=SegmentRef(
            transcript_ref=TranscriptRef(
                session_slug=session_slug,
                run_id=run_id,
                transcript_file_id=None,
                transcript_slug=index.transcript_slug,
            ),
            primary_locator="index",
            segment_index=idx,
            segment_id=None,
            timecode=segment.get("start"),
        ),
        transcript_title=index.transcript_slug,
        session_slug=session_slug,
        run_id=run_id,
        segment_id=None,
        segment_index=idx,
        segment_text=text,
        match_spans=match_spans,
        speaker_name=speaker_name,
        speaker_is_named=speaker_name not in ("", "Unknown"),
        start_time=float(segment.get("start", 0.0)),
        end_time=float(segment.get("end", 0.0)),
        context_indices=context_indices,
        context_before=before,
        context_after=after,
    )


@dataclass(frozen=True)
class _TranscriptIndex:
    session_name: str
    transcript_slug: str
    segments: List[Dict[str, object]]
    text_blob: str
    vocab: set[str]


@st.cache_data(show_spinner=False)
def _build_transcript_index(
    session_name: str,
    transcript_path: str,
    transcript_mtime: Optional[float],
) -> Optional[_TranscriptIndex]:
    transcript_data = FileService.load_transcript_by_session(session_name)
    if not transcript_data:
        return None
    segments = transcript_data.get("segments", [])
    if not isinstance(segments, list):
        return None
    source = transcript_data.get("source", {})
    if not isinstance(source, dict):
        source = {}
    original_path = source.get("original_path") or transcript_path
    transcript_slug = (
        Path(original_path).stem if original_path else session_name.split("/")[-1]
    )
    text_parts: List[str] = []
    vocab: set[str] = set()
    for segment in segments:
        text = segment.get("text", "")
        if not isinstance(text, str):
            continue
        lower_text = _normalize(text)
        text_parts.append(lower_text)
        vocab.update(_tokenize(lower_text))
    return _TranscriptIndex(
        session_name=session_name,
        transcript_slug=transcript_slug,
        segments=segments,
        text_blob=" ".join(text_parts),
        vocab=vocab,
    )


def _resolve_session_path_for_search(session_name: str) -> str:
    resolved = FileService.resolve_transcript_path(session_name)
    return str(resolved) if resolved else session_name


def _resolve_transcript_mtime(session_name: str) -> Optional[float]:
    """Prefer filesystem mtime of the resolved transcript path; avoid full JSON load."""
    resolved = FileService.resolve_transcript_path(session_name)
    if resolved is not None:
        try:
            if resolved.exists():
                return float(resolved.stat().st_mtime)
        except OSError:
            pass
    transcript_data = FileService.load_transcript_by_session(session_name)
    if not transcript_data:
        return None
    source = transcript_data.get("source", {})
    if isinstance(source, dict):
        mtime = source.get("file_mtime")
        if isinstance(mtime, (int, float)):
            return float(mtime)
    return None


@st.cache_data(ttl=60, show_spinner=False)
def get_speakers_from_transcripts(
    session_slugs: Optional[Tuple[str, ...]] = None,
) -> List[str]:
    sessions = cached_list_available_sessions()
    if session_slugs is not None:
        slug_set = set(session_slugs)
        sessions = [
            s
            for s in sessions
            if _session_slug_from_name(str(s.get("name") or "")) in slug_set
        ]
    names: set = set()
    for session_info in sessions:
        session_name = session_info.get("name", "")
        if not session_name:
            continue
        transcript_path = _resolve_session_path_for_search(session_name)
        transcript_mtime = _resolve_transcript_mtime(session_name)
        index = _build_transcript_index(session_name, transcript_path, transcript_mtime)
        if not index:
            continue
        segments = resolve_speaker_names_from_sidecars(index.segments, transcript_path)
        for seg in segments:
            n = seg.get("speaker_display") or seg.get("speaker") or ""
            if n and str(n).strip():
                names.add(str(n).strip())
    return sorted(names)


class SearchBackend(Protocol):
    def search_substring(
        self, query: str, filters: Optional[SearchFilters] = None
    ) -> Tuple[List[SearchResult], int]: ...


class FileSearchBackend:
    def search_substring(
        self, query: str, filters: Optional[SearchFilters] = None
    ) -> Tuple[List[SearchResult], int]:
        sessions = cached_list_available_sessions()
        results: List[SearchResult] = []
        for session_info in sessions:
            session_name = session_info.get("name", "")
            if not session_name:
                continue
            if not _session_matches_filters(session_name, filters):
                continue
            transcript_path = _resolve_session_path_for_search(session_name)
            transcript_mtime = _resolve_transcript_mtime(session_name)
            index = _build_transcript_index(
                session_name, transcript_path, transcript_mtime
            )
            if not index:
                continue
            segments = resolve_speaker_names_from_sidecars(
                index.segments, transcript_path
            )
            for idx, segment in enumerate(segments):
                if not _segment_matches_speaker_filters(segment, filters):
                    continue
                text = segment.get("text", "")
                if not isinstance(text, str):
                    continue
                matched = _match_segment_text(text, query)
                if matched is None:
                    continue
                match_spans, _is_phrase = matched
                results.append(
                    _build_search_result(
                        session_name=session_name,
                        index=index,
                        segments=segments,
                        idx=idx,
                        segment=segment,
                        text=text,
                        match_spans=match_spans,
                    )
                )
        return results, len(results)


class SearchService:
    def __init__(self) -> None:
        self._backend: Optional[SearchBackend] = None
        self._backend_kind: Optional[str] = None

    def _select_backend(self) -> SearchBackend:
        if self._backend is None:
            self._backend = FileSearchBackend()
            self._backend_kind = "file"
            st.session_state["search_backend_kind"] = "file"
        return self._backend

    def search_all_transcripts(
        self,
        query: str,
        filters: Optional[SearchFilters] = None,
        enable_fuzzy: bool = True,
    ) -> SearchResponse:
        backend = self._select_backend()
        substring_results, total_found = backend.search_substring(query, filters)
        ranked = self._rank_results(substring_results, query)
        total_found = len(ranked)
        cap = 200
        shown = ranked[:cap]
        total_shown = len(shown)

        fuzzy_results: List[SearchResult] = []
        fuzzy_ran = False
        fuzzy_reason: Optional[str] = None
        if enable_fuzzy:
            if len(query) < 4:
                fuzzy_reason = "query too short"
            elif len(ranked) >= 10:
                fuzzy_reason = "sufficient substring results"
            else:
                fuzzy_ran = True
                fuzzy_reason = "few substring results"
                candidates = self._select_candidate_transcripts(query, filters)
                fuzzy_results = self._fuzzy_search(candidates, query, filters=filters)
        total_found = len(ranked) + len(fuzzy_results)
        remaining = max(0, cap - total_shown)
        fuzzy_results = fuzzy_results[:remaining]
        total_shown = len(shown) + len(fuzzy_results)

        return SearchResponse(
            substring_results=shown,
            fuzzy_results=fuzzy_results,
            total_found=total_found,
            total_shown=total_shown,
            fuzzy_ran=fuzzy_ran,
            fuzzy_reason=fuzzy_reason,
        )

    def _select_candidate_transcripts(
        self, query: str, filters: Optional[SearchFilters] = None
    ) -> List[_TranscriptIndex]:
        tokens = _tokenize(query)
        if not tokens:
            return []
        candidates: List[_TranscriptIndex] = []
        for session_info in cached_list_available_sessions():
            session_name = session_info.get("name", "")
            if not session_name:
                continue
            if not _session_matches_filters(session_name, filters):
                continue
            transcript_path = _resolve_session_path_for_search(session_name)
            transcript_mtime = _resolve_transcript_mtime(session_name)
            index = _build_transcript_index(
                session_name, transcript_path, transcript_mtime
            )
            if not index:
                continue
            if any(
                token in index.text_blob or token in index.vocab for token in tokens
            ):
                candidates.append(index)
        return candidates

    def _fuzzy_search(
        self,
        candidates: List[_TranscriptIndex],
        query: str,
        threshold: float = 70.0,
        filters: Optional[SearchFilters] = None,
    ) -> List[SearchResult]:
        try:
            from rapidfuzz import fuzz  # type: ignore[import-not-found]
        except Exception:
            return []
        results: List[SearchResult] = []
        for index in candidates:
            if not _session_matches_filters(index.session_name, filters):
                continue
            transcript_path = _resolve_session_path_for_search(index.session_name)
            segments = resolve_speaker_names_from_sidecars(
                index.segments, transcript_path
            )
            for idx, segment in enumerate(segments):
                if not _segment_matches_speaker_filters(segment, filters):
                    continue
                text = segment.get("text", "")
                if not isinstance(text, str):
                    continue
                score = fuzz.partial_ratio(_normalize(query), _normalize(text))
                if score < threshold:
                    continue
                results.append(
                    _build_search_result(
                        session_name=index.session_name,
                        index=index,
                        segments=segments,
                        idx=idx,
                        segment=segment,
                        text=text,
                        match_spans=_find_spans(text, query),
                    )
                )
        return results

    def _rank_results(
        self, results: List[SearchResult], query: str
    ) -> List[SearchResult]:
        tokens = _tokenize(query)

        def sort_key(result: SearchResult) -> Tuple[int, int, int, int, int, int]:
            text = result.segment_text
            boundary_match = _is_word_boundary_match(text, query)
            # Phrase/substring ranks above token-AND-only hits.
            substring_match = _is_phrase_match(text, query)
            match_count = len(result.match_spans)
            first_pos = result.match_spans[0][0] if result.match_spans else len(text)
            length = len(text)
            speaker_bonus = 1 if result.speaker_is_named else 0
            meta_bonus = 0
            for token in tokens:
                token_re = re.compile(rf"(?<!\w){re.escape(token)}(?!\w)")
                if token_re.search(_normalize(result.speaker_name or "")):
                    meta_bonus = 1
                if token_re.search(_normalize(result.transcript_title or "")):
                    meta_bonus = 1
            return (
                0 if boundary_match else 1,
                0 if substring_match else 1,
                -match_count,
                first_pos,
                length,
                -(speaker_bonus + meta_bonus),
            )

        return sorted(results, key=sort_key)
