from __future__ import annotations

import numpy as np


def npvi(values: list[float]) -> float | None:
    """
    Normalized Pairwise Variability Index (nPVI).
    """
    if len(values) < 2:
        return None
    vals = np.asarray(values, dtype=np.float64)
    diffs = np.abs(np.diff(vals))
    denom = (vals[:-1] + vals[1:]) / 2.0
    valid = denom > 0
    if not np.any(valid):
        return None
    return float(100.0 * np.mean(diffs[valid] / denom[valid]))


def varco(values: list[float]) -> float | None:
    """
    Variability coefficient (VarcoV): 100 * std / mean.
    """
    if len(values) < 2:
        return None
    vals = np.asarray(values, dtype=np.float64)
    mean = float(np.mean(vals))
    if mean <= 0:
        return None
    return float(100.0 * np.std(vals) / mean)
