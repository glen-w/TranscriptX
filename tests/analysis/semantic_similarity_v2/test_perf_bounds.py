"""Perf smoke: candidate cap respected (marked slow)."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.semantic_similarity_v2.candidates import (
    generate_candidate_pairs,
)
from transcriptx.core.analysis.semantic_similarity_v2.intake import SegmentRow


@pytest.mark.semantic_v2_slow
def test_max_candidate_pairs_bounds_pairs() -> None:
    rows = [
        SegmentRow(str(i), "s", "S", float(i), float(i) + 0.5, "word " * 5, "word " * 5)
        for i in range(200)
    ]
    pairs, gen = generate_candidate_pairs(
        rows,
        self_window=1_000_000.0,
        cross_window=1_000_000.0,
        top_k_per_segment=500,
        max_candidate_pairs=50,
        use_lexical_prefilter=False,
        lexical_min_jaccard=0.0,
    )
    assert len(pairs) <= 50
    assert gen >= len(pairs)
