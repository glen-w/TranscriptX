"""Local span derivation, validation, and occurrence expansion for LLM suggestions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from transcriptx.core.corrections.detect import resolve_segment_id
from transcriptx.core.corrections.models import Candidate as EngineCandidate
from transcriptx.core.corrections.models import Occurrence
from transcriptx.services.corrections_studio.occurrence_keys import (
    stable_occurrence_key,
)


@dataclass
class GroundingResult:
    accepted: List[EngineCandidate]
    rejected: int
    raw_count: int


def _find_span(text: str, source: str) -> Optional[Tuple[int, int]]:
    if not source:
        return None
    idx = text.find(source)
    if idx >= 0:
        # Ambiguous if another match exists
        if text.find(source, idx + 1) >= 0:
            return None
        return (idx, idx + len(source))
    # Casefold fallback (unique match only) — aligns with merge/identity keys.
    src_cf = source.casefold()
    text_cf = text.casefold()
    idx_cf = text_cf.find(src_cf)
    if idx_cf >= 0 and text_cf.find(src_cf, idx_cf + 1) < 0:
        return (idx_cf, idx_cf + len(source))
    # Single-token case-insensitive whole-token
    if " " not in source.strip() and "\t" not in source:
        pattern = re.compile(rf"(?<!\w){re.escape(source)}(?!\w)", re.IGNORECASE)
        matches = list(pattern.finditer(text))
        if len(matches) == 1:
            m = matches[0]
            return (m.start(), m.end())
    return None


def _style_reject(source: str, replacement: str) -> bool:
    if source.strip() == replacement.strip():
        return True
    if len(source) > 80 or len(source.split()) > 8:
        return True
    return False


def _snippet(text: str, span: Tuple[int, int], radius: int = 40) -> str:
    a = max(0, span[0] - radius)
    b = min(len(text), span[1] + radius)
    return text[a:b]


def _resolve_segment_index(
    segment_ref: int | str,
    segments: Sequence[Dict[str, Any]],
    transcript_key: str,
    index_offset: int = 0,
) -> Optional[int]:
    if isinstance(segment_ref, int) or (
        isinstance(segment_ref, str) and segment_ref.isdigit()
    ):
        idx = int(segment_ref)
        # Prefer absolute indices when in range
        if 0 <= idx < len(segments):
            return idx
        # Chunk-local index
        local = idx if index_offset == 0 else idx
        abs_i = index_offset + local if index_offset else local
        if 0 <= abs_i < len(segments):
            return abs_i
        return None
    ref = str(segment_ref)
    for i, seg in enumerate(segments):
        sid = resolve_segment_id(seg, transcript_key, segment_index=i)
        if sid == ref or str(seg.get("id") or "") == ref:
            return i
    return None


def expand_occurrences(
    *,
    segments: Sequence[Dict[str, Any]],
    transcript_key: str,
    source_text: str,
    seed_index: int,
    seed_span: Tuple[int, int],
    max_occurrences: int = 50,
) -> List[Occurrence]:
    out: List[Occurrence] = []
    seen: set[tuple] = set()

    def add(i: int, span: Tuple[int, int]) -> None:
        seg = segments[i]
        text = str(seg.get("text") or "")
        sid = resolve_segment_id(seg, transcript_key, segment_index=i)
        key = (sid, span[0], span[1])
        if key in seen:
            return
        seen.add(key)
        sk = stable_occurrence_key(sid, span[0], span[1], source_text)
        out.append(
            Occurrence(
                segment_id=sid,
                speaker=seg.get("speaker"),
                time_start=seg.get("start"),
                time_end=seg.get("end"),
                span=span,
                snippet=_snippet(text, span),
                occurrence_id=sk,
            )
        )

    add(seed_index, seed_span)
    if len(out) >= max_occurrences:
        return out
    for i, seg in enumerate(segments):
        text = str(seg.get("text") or "")
        start = 0
        while True:
            pos = text.find(source_text, start)
            if pos < 0:
                break
            span = (pos, pos + len(source_text))
            add(i, span)
            if len(out) >= max_occurrences:
                return out
            start = pos + 1
    return out


def ground_discovery_candidates(
    raw_candidates: List[Dict[str, Any]],
    *,
    segments: Sequence[Dict[str, Any]],
    transcript_key: str,
    chunk_segment_indices: Optional[Sequence[int]] = None,
    max_per_chunk: int = 10,
) -> GroundingResult:
    accepted: List[EngineCandidate] = []
    rejected = 0
    index_offset = chunk_segment_indices[0] if chunk_segment_indices else 0

    for raw in raw_candidates[: max_per_chunk * 2]:
        if len(accepted) >= max_per_chunk:
            break
        source = str(raw.get("source_text") or "").strip()
        replacement = str(raw.get("replacement_text") or "").strip()
        if _style_reject(source, replacement):
            rejected += 1
            continue
        seg_i = _resolve_segment_index(
            raw.get("segment_ref"),
            segments,
            transcript_key,
            index_offset=index_offset,
        )
        # If chunk indices provided and ref looks local, map through them
        if seg_i is None and chunk_segment_indices:
            try:
                local = int(raw.get("segment_ref"))
                if 0 <= local < len(chunk_segment_indices):
                    seg_i = chunk_segment_indices[local]
                elif local in chunk_segment_indices:
                    seg_i = local
            except (TypeError, ValueError):
                seg_i = None
        if seg_i is None or not (0 <= seg_i < len(segments)):
            rejected += 1
            continue
        text = str(segments[seg_i].get("text") or "")
        span = _find_span(text, source)
        if span is None:
            rejected += 1
            continue
        # Prefer exact source as found in text
        found = text[span[0] : span[1]]
        occs = expand_occurrences(
            segments=segments,
            transcript_key=transcript_key,
            source_text=found,
            seed_index=seg_i,
            seed_span=span,
        )
        if not occs:
            rejected += 1
            continue
        accepted.append(
            EngineCandidate(
                proposed_wrong=found,
                proposed_right=replacement,
                kind="ner_variant",
                confidence=0.45,
                occurrences=occs,
            )
        )
    return GroundingResult(
        accepted=accepted, rejected=rejected, raw_count=len(raw_candidates)
    )
