# mypy: ignore-missing-imports
"""Search service for TranscriptX web UI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Protocol, Sequence, Tuple
import re

import streamlit as st

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import OUTPUTS_DIR
from transcriptx.web.models.search import (
    SearchFilters,
    SearchResponse,
    SearchResult,
    SegmentRef,
    TranscriptRef,
)
from transcriptx.web.services.file_service import FileService

logger = get_logger()


_WORD_BOUNDARY_RE = re.compile(r"\w")


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
    if " " in lower_query:
        return bool(pattern.search(lower_text))
    return bool(pattern.search(lower_text))


def _is_phrase_match(text: str, query: str) -> bool:
    lower_text = _normalize(text)
    lower_query = _normalize(query)
    return lower_query in lower_text


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
    transcript_data = FileService.load_transcript_data(session_name)
    if not transcript_data:
        return None
    segments = transcript_data.get("segments", [])
    if not isinstance(segments, list):
        return None
    source = transcript_data.get("source", {})
    if not isinstance(source, dict):
        source = {}
    original_path = source.get("original_path") or transcript_path
    transcript_slug = Path(original_path).stem if original_path else session_name.split("/")[-1]
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


def _resolve_transcript_path(session_name: str) -> Optional[str]:
    session_dir = FileService._resolve_session_dir(session_name)
    manifest_path = session_dir / ".transcriptx" / "manifest.json"
    if manifest_path.exists():
        try:
            import json

            with open(manifest_path, "r", encoding="utf-8") as handle:
                manifest = json.load(handle)
            transcript_path = manifest.get("transcript_path")
            if transcript_path:
                return str(Path(transcript_path).resolve())
        except Exception as exc:
            logger.warning(f"Failed to read manifest for {session_name}: {exc}")
    return None


def _resolve_transcript_mtime(session_name: str) -> Optional[float]:
    transcript_data = FileService.load_transcript_data(session_name)
    if not transcript_data:
        return None
    source = transcript_data.get("source", {})
    if isinstance(source, dict):
        mtime = source.get("file_mtime")
        if isinstance(mtime, (int, float)):
            return float(mtime)
    return None


class SearchBackend(Protocol):
    def search_substring(
        self, query: str, filters: Optional[SearchFilters] = None
    ) -> Tuple[List[SearchResult], int]:
        ...


class DbSearchBackend:
    """Database-backed search implementation."""

    def __init__(self) -> None:
        from transcriptx.database import get_session
        from transcriptx.database.models import Speaker, TranscriptFile, TranscriptSegment

        self._get_session = get_session
        self._TranscriptSegment = TranscriptSegment
        self._TranscriptFile = TranscriptFile
        self._Speaker = Speaker

    def _build_text_query(self, query: str) -> Tuple[str, str]:
        return f"%{query}%", "ilike"

    def resolve_session_run_map(
        self, transcript_file_ids: List[int]
    ) -> Dict[int, TranscriptRef]:
        session = self._get_session()
        try:
            files = (
                session.query(self._TranscriptFile)
                .filter(self._TranscriptFile.id.in_(transcript_file_ids))
                .all()
            )
        finally:
            session.close()

        path_map = _build_transcript_path_map()
        resolved: Dict[int, TranscriptRef] = {}
        for item in files:
            transcript_path = str(Path(item.file_path).resolve())
            ref = path_map.get(transcript_path)
            if not ref:
                transcript_slug = Path(item.file_path).stem
                ref = TranscriptRef(
                    session_slug="unknown",
                    run_id="unknown",
                    transcript_file_id=item.id,
                    transcript_slug=transcript_slug,
                )
            resolved[item.id] = ref
        return resolved

    def search_substring(
        self, query: str, filters: Optional[SearchFilters] = None
    ) -> Tuple[List[SearchResult], int]:
        session = self._get_session()
        try:
            like_query, mode = self._build_text_query(query)
            q = (
                session.query(self._TranscriptSegment, self._TranscriptFile, self._Speaker)
                .join(self._TranscriptFile)
                .outerjoin(self._Speaker)
            )
            if mode == "ilike":
                q = q.filter(self._TranscriptSegment.text.ilike(like_query))
            segments = q.all()
        finally:
            session.close()

        transcript_ids = list({item[1].id for item in segments})
        ref_map = self.resolve_session_run_map(transcript_ids)
        results: List[SearchResult] = []
        for segment, transcript_file, speaker in segments:
            if segment.segment_index is None:
                raise ValueError("TranscriptSegment missing segment_index.")
            ref = ref_map.get(transcript_file.id)
            if not ref:
                continue
            segment_ref = SegmentRef(
                transcript_ref=ref,
                primary_locator="db_id",
                segment_id=segment.id,
                segment_index=segment.segment_index,
                timecode=segment.start_time,
            )
            speaker_name = speaker.name if speaker and speaker.name else "Unknown"
            match_spans = _find_spans(segment.text, query)
            results.append(
                SearchResult(
                    segment_ref=segment_ref,
                    transcript_title=ref.transcript_slug or transcript_file.file_name,
                    session_slug=ref.session_slug,
                    run_id=ref.run_id,
                    segment_id=segment.id,
                    segment_index=segment.segment_index,
                    segment_text=segment.text,
                    match_spans=match_spans,
                    speaker_name=speaker_name,
                    speaker_is_named=speaker_name not in ("", "Unknown"),
                    start_time=segment.start_time,
                    end_time=segment.end_time,
                    context_indices=(
                        segment.segment_index - 1,
                        segment.segment_index + 1,
                    ),
                )
            )
        return results, len(results)


class FileSearchBackend:
    """File-based search fallback."""

    def search_substring(
        self, query: str, filters: Optional[SearchFilters] = None
    ) -> Tuple[List[SearchResult], int]:
        sessions = FileService.list_available_sessions()
        results: List[SearchResult] = []
        for session_info in sessions:
            session_name = session_info.get("name", "")
            if not session_name:
                continue
            transcript_path = _resolve_transcript_path(session_name) or session_name
            transcript_mtime = _resolve_transcript_mtime(session_name)
            index = _build_transcript_index(session_name, transcript_path, transcript_mtime)
            if not index:
                continue
            # Lazy import to avoid circular dependency
            from transcriptx.web.utils import resolve_speaker_names_from_db
            segments = resolve_speaker_names_from_db(index.segments, session_name)
            for idx, segment in enumerate(segments):
                text = segment.get("text", "")
                if not isinstance(text, str):
                    continue
                if _normalize(query) not in _normalize(text):
                    continue
                match_spans = _find_spans(text, query)
                speaker_name = (
                    segment.get("speaker_display")
                    or segment.get("speaker")
                    or "Unknown"
                )
                session_slug, run_id = session_name.split("/", 1)
                segment_ref = SegmentRef(
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
                )
                results.append(
                    SearchResult(
                        segment_ref=segment_ref,
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
                        context_indices=(max(0, idx - 1), idx + 1),
                    )
                )
        return results, len(results)


@st.cache_data(show_spinner=False)
def _build_transcript_path_map() -> Dict[str, TranscriptRef]:
    path_map: Dict[str, TranscriptRef] = {}
    for session_info in FileService.list_available_sessions():
        session_name = session_info.get("name", "")
        if not session_name or "/" not in session_name:
            continue
        session_slug, run_id = session_name.split("/", 1)
        transcript_path = _resolve_transcript_path(session_name)
        if not transcript_path:
            continue
        transcript_slug = Path(transcript_path).stem
        path_map[str(Path(transcript_path).resolve())] = TranscriptRef(
            session_slug=session_slug,
            run_id=run_id,
            transcript_file_id=None,
            transcript_slug=transcript_slug,
        )
    return path_map


class SearchService:
    def __init__(self) -> None:
        self._backend: Optional[SearchBackend] = None
        self._backend_kind: Optional[str] = None

    def _select_backend(self) -> object:
        if self._backend is not None:
            return self._backend
        backend_kind = st.session_state.get("search_backend_kind")
        if backend_kind == "db":
            self._backend = DbSearchBackend()
            return self._backend
        if backend_kind == "file":
            self._backend = FileSearchBackend()
            return self._backend
        if self._db_available():
            backend_kind = "db"
            self._backend = DbSearchBackend()
        else:
            backend_kind = "file"
            self._backend = FileSearchBackend()
        st.session_state["search_backend_kind"] = backend_kind
        self._backend_kind = backend_kind
        return self._backend

    def _db_available(self) -> bool:
        try:
            backend = DbSearchBackend()
            session = backend._get_session()
            try:
                session.query(backend._TranscriptSegment).limit(1).all()
            finally:
                session.close()
            return True
        except Exception:
            return False

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
                candidates = self._select_candidate_transcripts(query)
                fuzzy_results = self._fuzzy_search(candidates, query)
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

    def _select_candidate_transcripts(self, query: str) -> List[_TranscriptIndex]:
        tokens = _tokenize(query)
        if not tokens:
            return []
        candidates: List[_TranscriptIndex] = []
        for session_info in FileService.list_available_sessions():
            session_name = session_info.get("name", "")
            if not session_name:
                continue
            transcript_path = _resolve_transcript_path(session_name) or session_name
            transcript_mtime = _resolve_transcript_mtime(session_name)
            index = _build_transcript_index(session_name, transcript_path, transcript_mtime)
            if not index:
                continue
            if any(token in index.text_blob or token in index.vocab for token in tokens):
                candidates.append(index)
        return candidates

    def _fuzzy_search(
        self,
        candidates: List[_TranscriptIndex],
        query: str,
        threshold: float = 70.0,
    ) -> List[SearchResult]:
        try:
            from rapidfuzz import fuzz  # type: ignore[import-not-found]
        except Exception:
            return []
        results: List[SearchResult] = []
        # Lazy import to avoid circular dependency
        from transcriptx.web.utils import resolve_speaker_names_from_db
        for index in candidates:
            session_slug, run_id = index.session_name.split("/", 1)
            segments = resolve_speaker_names_from_db(index.segments, index.session_name)
            for idx, segment in enumerate(segments):
                text = segment.get("text", "")
                if not isinstance(text, str):
                    continue
                score = fuzz.partial_ratio(_normalize(query), _normalize(text))
                if score < threshold:
                    continue
                speaker_name = (
                    segment.get("speaker_display")
                    or segment.get("speaker")
                    or "Unknown"
                )
                segment_ref = SegmentRef(
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
                )
                results.append(
                    SearchResult(
                        segment_ref=segment_ref,
                        transcript_title=index.transcript_slug,
                        session_slug=session_slug,
                        run_id=run_id,
                        segment_id=None,
                        segment_index=idx,
                        segment_text=text,
                        match_spans=_find_spans(text, query),
                        speaker_name=speaker_name,
                        speaker_is_named=speaker_name not in ("", "Unknown"),
                        start_time=float(segment.get("start", 0.0)),
                        end_time=float(segment.get("end", 0.0)),
                        context_indices=(max(0, idx - 1), idx + 1),
                    )
                )
        return results

    def _rank_results(
        self, results: List[SearchResult], query: str
    ) -> List[SearchResult]:
        tokens = _tokenize(query)
        lower_query = _normalize(query)

        def sort_key(result: SearchResult) -> Tuple[int, int, int, int, int, int]:
            text = result.segment_text
            boundary_match = _is_word_boundary_match(text, query)
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
