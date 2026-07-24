"""Vectorized cosine similarity via L2-normalized dot products."""

from __future__ import annotations

from typing import List, Tuple

import numpy as np


def score_pairs(
    e_rows: np.ndarray,
    pairs: List[Tuple[int, int]],
) -> List[float]:
    """``e_rows`` must be L2-normalized; cosine = dot."""
    scores: list[float] = []
    for i, j in pairs:
        scores.append(float(np.dot(e_rows[i], e_rows[j])))
    return scores
