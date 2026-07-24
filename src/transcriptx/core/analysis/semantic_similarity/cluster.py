"""Lightweight clustering on embedding rows (DBSCAN when sklearn available)."""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np

STATUS_OK = "ok"
STATUS_INSUFFICIENT = "insufficient_rows"
STATUS_DEPENDENCY = "dependency_missing"
STATUS_FAILED = "clustering_failed"


def _all_noise(n: int, *, status: str, reason: str | None = None) -> Dict[str, Any]:
    labels: List[int] = [-1] * int(n)
    out: Dict[str, Any] = {
        "labels": labels,
        "n_clusters": 0,
        "status": status,
    }
    if reason:
        out["reason"] = reason
    return out


def cluster_embeddings(
    e_rows: np.ndarray,
    *,
    min_samples: int = 2,
    eps: float = 0.35,
) -> Dict[str, Any]:
    """
    Run DBSCAN on L2-normalized rows.

    Always returns ``labels`` with length equal to the eligible-row count.
    Dependency or clustering failures yield all-noise labels plus an explicit
    status — never a fabricated single cluster.
    """
    n = int(len(e_rows))
    if n < int(min_samples):
        return _all_noise(n, status=STATUS_INSUFFICIENT, reason="n_lt_min_samples")
    try:
        from sklearn.cluster import DBSCAN
    except Exception as exc:  # noqa: BLE001 — dependency surface
        return _all_noise(
            n, status=STATUS_DEPENDENCY, reason=f"sklearn_import:{type(exc).__name__}"
        )
    try:
        labels = DBSCAN(
            eps=float(eps), min_samples=int(min_samples), metric="cosine"
        ).fit_predict(e_rows)
        label_list = [int(x) for x in labels.tolist()]
        if len(label_list) != n:
            return _all_noise(n, status=STATUS_FAILED, reason="label_length_mismatch")
        n_clusters = len({x for x in label_list if x >= 0})
        return {
            "labels": label_list,
            "n_clusters": int(n_clusters),
            "status": STATUS_OK,
        }
    except Exception as exc:  # noqa: BLE001 — keep pipeline soft-fail
        return _all_noise(n, status=STATUS_FAILED, reason=f"{type(exc).__name__}:{exc}")
