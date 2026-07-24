"""Candidate pair generation with time-window break and caps."""

from __future__ import annotations

from typing import List, Tuple

from .intake import SegmentRow


def jaccard_tokens(a: str, b: str) -> float:
    ta = set(a.split())
    tb = set(b.split())
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


def generate_candidate_pairs(
    rows: List[SegmentRow],
    *,
    self_window: float,
    cross_window: float,
    top_k_per_segment: int,
    max_candidate_pairs: int,
    use_lexical_prefilter: bool,
    lexical_min_jaccard: float,
) -> Tuple[List[Tuple[int, int]], int]:
    """
    Return (pairs as segment indices (i,j) with i<j), total_generated_before_cap.

    Rows must be sorted by start time. Uses **break** (not continue) when the
    forward scan leaves the time window for ordered same-speaker streams.
    """
    n = len(rows)
    pairs: list[tuple[int, int]] = []
    generated = 0
    per_i: dict[int, int] = {}
    max_w = max(self_window, cross_window)

    def cap_reached() -> bool:
        return len(pairs) >= max_candidate_pairs

    for i in range(n):
        per_i[i] = 0
        ri = rows[i]
        for j in range(i + 1, n):
            if cap_reached():
                return pairs, generated
            rj = rows[j]
            dt = rj.start - ri.start
            if dt > max_w:
                break
            same = ri.speaker_key == rj.speaker_key
            if same:
                if dt > self_window:
                    continue
            else:
                if dt > cross_window:
                    continue
            generated += 1
            if use_lexical_prefilter:
                if jaccard_tokens(ri.normalized, rj.normalized) < lexical_min_jaccard:
                    continue
            if per_i[i] >= top_k_per_segment:
                break
            pairs.append((i, j))
            per_i[i] += 1
            if cap_reached():
                return pairs, generated

    return pairs, generated
