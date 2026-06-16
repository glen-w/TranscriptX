"""Cosine via dot matches sklearn reference on small matrices."""

from __future__ import annotations

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from transcriptx.core.analysis.semantic_similarity_v2.similarity import score_pairs


def test_dot_equals_sklearn_cosine_for_normalized_rows() -> None:
    rng = np.random.default_rng(0)
    e = rng.normal(size=(5, 8))
    e = e / np.linalg.norm(e, axis=1, keepdims=True)
    pairs = [(0, 1), (2, 4)]
    dots = score_pairs(e, pairs)
    for k, (i, j) in enumerate(pairs):
        ref = cosine_similarity(e[i : i + 1], e[j : j + 1])[0, 0]
        assert abs(dots[k] - ref) < 1e-6
