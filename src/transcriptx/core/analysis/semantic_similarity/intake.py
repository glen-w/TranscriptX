"""Segment intake, normalization, eligibility, deduplication."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


@dataclass(frozen=True)
class SegmentRow:
    segment_id: str
    speaker_key: str
    display_name: str
    start: float
    end: float
    text: str
    normalized: str
    source_index: int


_FILLER_RE = re.compile(
    r"^\s*(um+|uh+|like|you know|i mean|sort of|kind of)[\s,.\?!]*$", re.I
)


def normalize_text(text: str) -> str:
    t = " ".join(text.lower().split())
    return t


def segment_rows_from_dicts(
    segments: List[Dict[str, Any]],
    *,
    min_words: int,
) -> Tuple[List[SegmentRow], Dict[str, Any]]:
    """Build typed rows; skip empty / too-short / obvious filler-only lines."""
    skipped: Dict[str, int] = {"too_short": 0, "empty": 0, "filler": 0}
    rows: list[SegmentRow] = []
    for i, seg in enumerate(segments):
        text = (seg.get("text") or "").strip()
        if not text:
            skipped["empty"] += 1
            continue
        if _FILLER_RE.match(text):
            skipped["filler"] += 1
            continue
        words = text.split()
        if len(words) < min_words:
            skipped["too_short"] += 1
            continue
        sid = str(seg.get("id", seg.get("segment_id", i)))
        spk_db = seg.get("speaker_db_id")
        speaker_key = str(spk_db) if spk_db is not None else str(seg.get("speaker", ""))
        display = str(seg.get("speaker", speaker_key))
        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", start))
        norm = normalize_text(text)
        rows.append(
            SegmentRow(
                segment_id=sid,
                speaker_key=speaker_key,
                display_name=display,
                start=start,
                end=end,
                text=text,
                normalized=norm,
                source_index=int(i),
            )
        )
    rows.sort(key=lambda r: (r.start, r.source_index, r.segment_id))
    return rows, {"skipped_reasons": skipped}


def dedupe_text_index(rows: List[SegmentRow]) -> Dict[str, int]:
    """Map normalized text -> first row index (unique embedding keys)."""
    out: dict[str, int] = {}
    for idx, r in enumerate(rows):
        if r.normalized not in out:
            out[r.normalized] = idx
    return out
