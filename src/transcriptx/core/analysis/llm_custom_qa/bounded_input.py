"""Token-aware bounded input + coordinate map for grounding."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Any, Optional

from transcriptx.core.analysis.llm_custom_qa.constants import (
    GROUNDING_SEGMENT_SEPARATOR,
)
from transcriptx.core.analysis.llm_support.hashing import sha256_text


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


def build_grounding_corpus(
    segments: list[dict[str, Any]],
    *,
    max_corpus_chars: int,
) -> BoundedGroundingCorpus:
    """Pack transcript segments into a grounding corpus with coordinate maps.

    Join with GROUNDING_SEGMENT_SEPARATOR. Never infer membership via substring
    search of a truncated prompt — membership comes from this offset map.
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

    entries: list[SegmentMapEntry] = []
    parts: list[str] = []
    cursor = 0
    truncated = False
    partial_final = False
    used_chars = 0

    for canonical_index, (orig_i, text, start, end) in enumerate(usable):
        piece = text if not parts else sep + text
        if max_corpus_chars >= 0 and cursor + len(piece) > max_corpus_chars:
            remaining = max_corpus_chars - cursor
            if remaining <= 0:
                truncated = True
                break
            # Partial final segment
            if parts:
                # need room for separator + some text
                if remaining <= len(sep):
                    truncated = True
                    break
                take = remaining - len(sep)
                if take <= 0:
                    truncated = True
                    break
                partial = text[:take]
                piece = sep + partial
                partial_final = True
            else:
                take = remaining
                partial = text[:take]
                piece = partial
                partial_final = take < len(text)
            truncated = True
            start_off = cursor + (len(sep) if parts else 0)
            end_off = cursor + len(piece)
            entries.append(
                SegmentMapEntry(
                    canonical_index=len(entries),
                    original_segment_index=orig_i,
                    text=partial,
                    start_time=start,
                    end_time=end,
                    corpus_start=start_off,
                    corpus_end=end_off,
                    prompt_start=start_off,
                    prompt_end=end_off,
                )
            )
            parts.append(piece if not parts else partial)
            # Fix parts list: store only segment text without leading sep
            if len(parts) == 1 and piece == partial:
                pass
            else:
                parts[-1] = partial if parts else partial
            # Rebuild corpus cleanly
            texts = [e.text for e in entries]
            corpus_text = sep.join(texts)
            used_chars = len(corpus_text)
            # recompute offsets
            entries = _recompute_offsets(entries, sep)
            return BoundedGroundingCorpus(
                corpus_text=corpus_text,
                entries=entries,
                input_chars_total=total_chars,
                input_chars_used=used_chars,
                truncated=True,
                partial_final_segment=partial_final,
                segments_total=len(segments),
                segments_used=len(entries),
                segments_omitted_empty=omitted_empty,
                segments_omitted_invalid=omitted_invalid,
                transcript_fingerprint=fingerprint,
                bounded_input_fingerprint=sha256_text(corpus_text),
            )

        start_off = cursor + (len(sep) if parts else 0)
        end_off = cursor + len(piece)
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

    corpus_text = sep.join(parts)
    used_chars = len(corpus_text)
    return BoundedGroundingCorpus(
        corpus_text=corpus_text,
        entries=entries,
        input_chars_total=total_chars,
        input_chars_used=used_chars,
        truncated=truncated,
        partial_final_segment=partial_final,
        segments_total=len(segments),
        segments_used=len(entries),
        segments_omitted_empty=omitted_empty,
        segments_omitted_invalid=omitted_invalid,
        transcript_fingerprint=fingerprint,
        bounded_input_fingerprint=sha256_text(corpus_text) if corpus_text else sha256_text(""),
    )


def _recompute_offsets(
    entries: list[SegmentMapEntry], sep: str
) -> list[SegmentMapEntry]:
    out: list[SegmentMapEntry] = []
    cursor = 0
    for i, entry in enumerate(entries):
        if i == 0:
            start = 0
            end = len(entry.text)
        else:
            start = cursor + len(sep)
            end = start + len(entry.text)
        out.append(
            SegmentMapEntry(
                canonical_index=i,
                original_segment_index=entry.original_segment_index,
                text=entry.text,
                start_time=entry.start_time,
                end_time=entry.end_time,
                corpus_start=start,
                corpus_end=end,
                prompt_start=start,
                prompt_end=end,
            )
        )
        cursor = end
    return out


def coverage_dict(corpus: BoundedGroundingCorpus, *, empty_run: bool = False) -> dict[str, Any]:
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
