"""Candidate generation uses time-window break semantics."""

from __future__ import annotations

from transcriptx.core.analysis.semantic_similarity_v2.candidates import (
    generate_candidate_pairs,
)
from transcriptx.core.analysis.semantic_similarity_v2.intake import SegmentRow


def test_time_window_stops_forward_scan() -> None:
    rows = [
        SegmentRow("0", "a", "A", 0.0, 1.0, "x y z", "x y z", 0),
        SegmentRow("1", "a", "A", 10.0, 11.0, "a b c", "a b c", 1),
        SegmentRow("2", "a", "A", 1000.0, 1001.0, "d e f", "d e f", 2),
    ]
    pairs, _ = generate_candidate_pairs(
        rows,
        self_window=50.0,
        cross_window=50.0,
        top_k_per_segment=10,
        max_candidate_pairs=10_000,
        use_lexical_prefilter=False,
        lexical_min_jaccard=0.0,
    )
    assert pairs == [(0, 1)]
