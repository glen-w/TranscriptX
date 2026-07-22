"""Deterministic keyword hints per final coverage span."""

from __future__ import annotations

from collections import Counter
from typing import Sequence

from transcriptx.core.analysis.topic_shift.segments import (
    CanonicalTopicSegment,
    lexical_tokens,
)


def keyword_hints_for_segments(
    segs: Sequence[CanonicalTopicSegment],
    *,
    max_hints: int = 8,
) -> list[str]:
    counts: Counter[str] = Counter()
    for seg in segs:
        counts.update(lexical_tokens(seg.raw_text))
    # Stable: count desc, then token asc
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [tok for tok, _ in ranked[: max(0, int(max_hints))]]


def hints_for_span_ranges(
    segments: Sequence[CanonicalTopicSegment],
    ranges: Sequence[tuple[int, int]],
    *,
    max_hints: int = 8,
) -> list[list[str]]:
    ordered = list(segments)
    out: list[list[str]] = []
    for c0, c1 in ranges:
        segs = [s for s in ordered if c0 <= s.canonical_position <= c1]
        out.append(keyword_hints_for_segments(segs, max_hints=max_hints))
    return out
