"""Token-aware bounded input + coordinate map for grounding."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from transcriptx.core.analysis.llm_custom_qa.constants import (
    GROUNDING_SEGMENT_SEPARATOR,
)
from transcriptx.core.analysis.llm_support.hashing import sha256_text

CorpusPrefer = Literal["head", "tail"]


@dataclass(frozen=True)
class SegmentMapEntry:
    canonical_index: int
    original_segment_index: int
    text: str
    start_time: Optional[float]
    end_time: Optional[float]
    corpus_start: int
    corpus_end: int
    prompt_start: int
    prompt_end: int


@dataclass
class BoundedGroundingCorpus:
    corpus_text: str
    entries: list[SegmentMapEntry] = field(default_factory=list)
    input_chars_total: int = 0
    input_chars_used: int = 0
    truncated: bool = False
    partial_final_segment: bool = False
    segments_total: int = 0
    segments_used: int = 0
    segments_omitted_empty: int = 0
    segments_omitted_invalid: int = 0
    transcript_fingerprint: str = ""
    bounded_input_fingerprint: str = ""

    @property
    def coverage_ratio(self) -> Optional[float]:
        if self.input_chars_total <= 0:
            return None
        return self.input_chars_used / float(self.input_chars_total)


def _segment_text(seg: Any) -> str:
    if not isinstance(seg, dict):
        return ""
    for key in ("text", "content", "utterance"):
        value = seg.get(key)
        if isinstance(value, str):
            return unicodedata.normalize("NFC", value)
    return ""


def _segment_times(seg: dict[str, Any]) -> tuple[Optional[float], Optional[float]]:
    start = seg.get("start")
    end = seg.get("end")
    try:
        start_f = float(start) if start is not None else None
    except (TypeError, ValueError):
        start_f = None
    try:
        end_f = float(end) if end is not None else None
    except (TypeError, ValueError):
        end_f = None
    return start_f, end_f


def _pack_entries(
    selected: list[tuple[int, str, Optional[float], Optional[float]]],
    *,
    sep: str,
) -> tuple[str, list[SegmentMapEntry]]:
    entries: list[SegmentMapEntry] = []
    parts: list[str] = []
    cursor = 0
    for orig_i, text, start, end in selected:
        start_off = 0 if not parts else cursor + len(sep)
        end_off = start_off + len(text)
        entries.append(
            SegmentMapEntry(
                canonical_index=len(entries),
                original_segment_index=orig_i,
                text=text,
                start_time=start,
                end_time=end,
                corpus_start=start_off,
                corpus_end=end_off,
                prompt_start=start_off,
                prompt_end=end_off,
            )
        )
        parts.append(text)
        cursor = end_off
    return sep.join(parts), entries


def _select_head_window(
    usable: list[tuple[int, str, Optional[float], Optional[float]]],
    *,
    max_corpus_chars: int,
    sep: str,
) -> tuple[list[tuple[int, str, Optional[float], Optional[float]]], bool, bool]:
    """Keep meeting prefix; may partially cut the newest kept segment."""
    selected: list[tuple[int, str, Optional[float], Optional[float]]] = []
    used = 0
    partial = False
    for orig_i, text, start, end in usable:
        extra = len(text) if not selected else len(sep) + len(text)
        if used + extra <= max_corpus_chars:
            selected.append((orig_i, text, start, end))
            used += extra
            continue
        remaining = max_corpus_chars - used
        if selected:
            remaining -= len(sep)
        if remaining <= 0:
            break
        partial_text = text[:remaining]
        if not partial_text:
            break
        selected.append((orig_i, partial_text, start, end))
        partial = True
        break
    truncated = partial or len(selected) < len(usable)
    return selected, truncated, partial


def _select_tail_window(
    usable: list[tuple[int, str, Optional[float], Optional[float]]],
    *,
    max_corpus_chars: int,
    sep: str,
) -> tuple[list[tuple[int, str, Optional[float], Optional[float]]], bool, bool]:
    """Keep meeting suffix; may partially cut the oldest kept segment.

    Preferring the tail keeps end-of-meeting evidence available for cite-or-
    unavailable QA when the full transcript exceeds the citation budget.
    """
    selected_rev: list[tuple[int, str, Optional[float], Optional[float]]] = []
    used = 0
    partial = False
    for orig_i, text, start, end in reversed(usable):
        extra = len(text) if not selected_rev else len(sep) + len(text)
        if used + extra <= max_corpus_chars:
            selected_rev.append((orig_i, text, start, end))
            used += extra
            continue
        remaining = max_corpus_chars - used
        if selected_rev:
            remaining -= len(sep)
        if remaining <= 0:
            break
        # Keep the suffix of the older segment so it stays contiguous with newer text.
        partial_text = text[-remaining:]
        if not partial_text:
            break
        selected_rev.append((orig_i, partial_text, start, end))
        partial = True
        break
    selected = list(reversed(selected_rev))
    truncated = partial or len(selected) < len(usable)
    return selected, truncated, partial


def build_grounding_corpus(
    segments: list[dict[str, Any]],
    *,
    max_corpus_chars: int,
    prefer: CorpusPrefer = "tail",
) -> BoundedGroundingCorpus:
    """Pack transcript segments into a grounding corpus with coordinate maps.

    Join with GROUNDING_SEGMENT_SEPARATOR. Never infer membership via substring
    search of a truncated prompt — membership comes from this offset map.

    When ``max_corpus_chars`` forces truncation, ``prefer="tail"`` keeps the
    end of the meeting (default; better for meeting QA) and ``prefer="head"``
    keeps the beginning.
    """
    sep = GROUNDING_SEGMENT_SEPARATOR
    usable: list[tuple[int, str, Optional[float], Optional[float]]] = []
    omitted_empty = 0
    omitted_invalid = 0
    for i, seg in enumerate(segments):
        if not isinstance(seg, dict):
            omitted_invalid += 1
            continue
        text = _segment_text(seg).strip()
        if not text:
            omitted_empty += 1
            continue
        start, end = _segment_times(seg)
        usable.append((i, text, start, end))

    full_parts = [t for _, t, _, _ in usable]
    full_corpus = sep.join(full_parts)
    total_chars = len(full_corpus)
    fingerprint = sha256_text(full_corpus) if full_corpus else sha256_text("")

    if max_corpus_chars < 0 or total_chars <= max_corpus_chars:
        corpus_text, entries = _pack_entries(usable, sep=sep)
        return BoundedGroundingCorpus(
            corpus_text=corpus_text,
            entries=entries,
            input_chars_total=total_chars,
            input_chars_used=len(corpus_text),
            truncated=False,
            partial_final_segment=False,
            segments_total=len(segments),
            segments_used=len(entries),
            segments_omitted_empty=omitted_empty,
            segments_omitted_invalid=omitted_invalid,
            transcript_fingerprint=fingerprint,
            bounded_input_fingerprint=(
                sha256_text(corpus_text) if corpus_text else sha256_text("")
            ),
        )

    if prefer == "head":
        selected, truncated, partial = _select_head_window(
            usable, max_corpus_chars=max_corpus_chars, sep=sep
        )
    else:
        selected, truncated, partial = _select_tail_window(
            usable, max_corpus_chars=max_corpus_chars, sep=sep
        )

    corpus_text, entries = _pack_entries(selected, sep=sep)
    return BoundedGroundingCorpus(
        corpus_text=corpus_text,
        entries=entries,
        input_chars_total=total_chars,
        input_chars_used=len(corpus_text),
        truncated=truncated,
        partial_final_segment=partial,
        segments_total=len(segments),
        segments_used=len(entries),
        segments_omitted_empty=omitted_empty,
        segments_omitted_invalid=omitted_invalid,
        transcript_fingerprint=fingerprint,
        bounded_input_fingerprint=(
            sha256_text(corpus_text) if corpus_text else sha256_text("")
        ),
    )


def coverage_dict(
    corpus: BoundedGroundingCorpus, *, empty_run: bool = False
) -> dict[str, Any]:
    ratio = None if empty_run else corpus.coverage_ratio
    if empty_run:
        return {
            "version": 1,
            "input_chars_total": 0,
            "input_chars_used": 0,
            "input_coverage_ratio": None,
            "truncated": False,
            "segments_total": 0,
            "segments_used": 0,
            "segments_omitted_empty": 0,
            "segments_omitted_invalid": 0,
            "partial_final_segment": False,
            "transcript_fingerprint": None,
            "bounded_input_fingerprint": None,
        }
    return {
        "version": 1,
        "input_chars_total": corpus.input_chars_total,
        "input_chars_used": corpus.input_chars_used,
        "input_coverage_ratio": ratio,
        "truncated": corpus.truncated,
        "segments_total": corpus.segments_total,
        "segments_used": corpus.segments_used,
        "segments_omitted_empty": corpus.segments_omitted_empty,
        "segments_omitted_invalid": corpus.segments_omitted_invalid,
        "partial_final_segment": corpus.partial_final_segment,
        "transcript_fingerprint": corpus.transcript_fingerprint or None,
        "bounded_input_fingerprint": corpus.bounded_input_fingerprint or None,
    }
