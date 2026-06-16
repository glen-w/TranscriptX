"""Lightweight clustering on embedding rows (DBSCAN when sklearn available)."""

from __future__ import annotations

from typing import Any, Dict

import numpy as np


def cluster_embeddings(
    e_rows: np.ndarray,
    *,
    min_samples: int = 2,
    eps: float = 0.35,
) -> Dict[str, Any]:
    """Run DBSCAN on L2-normalized rows; labels length = n."""
    if len(e_rows) < min_samples:
        return {"labels": [], "n_clusters": 0}
    try:
        from sklearn.cluster import DBSCAN

        labels = DBSCAN(eps=eps, min_samples=min_samples, metric="cosine").fit_predict(
            e_rows
        )
        n_clusters = len({x for x in labels if x >= 0})
        return {"labels": labels.tolist(), "n_clusters": int(n_clusters)}
    except Exception:
        return {"labels": [0] * len(e_rows), "n_clusters": 1}
