"""Change-point detector with locked peak / threshold / centroid semantics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from transcriptx.core.analysis.topic_shift.semantics import (
    DEFAULT_CENTROID_RADIUS,
    DEFAULT_CENTROID_THRESHOLD,
    DEFAULT_EDGE_EXCLUDE,
    DEFAULT_FLOAT_DECIMALS,
    DEFAULT_MAX_SHIFTS,
    DEFAULT_MIN_GAP_SECONDS,
    DEFAULT_MIN_GAP_WINDOWS,
    DEFAULT_SMOOTH_WIDTH,
)
from transcriptx.core.analysis.topic_shift.windowing import TopicWindow


@dataclass(frozen=True)
class DetectorThresholds:
    k_mad: float
    absolute_floor: float
    min_prominence: float


@dataclass(frozen=True)
class PeakCandidate:
    distance_index: int  # boundary between windows i and i+1
    raw_distance: float
    smoothed_distance: float
    local_prominence: float
    decision_threshold: float
    normalized_strength: float
    time: float
    accepted: bool
    reject_reason: str | None = None


def round_metric(value: float, decimals: int = DEFAULT_FLOAT_DECIMALS) -> float:
    return float(round(float(value), decimals))


def consecutive_distances(embeddings: np.ndarray) -> np.ndarray:
    """raw_distance[i] = 1 - cosine(e[i], e[i+1]) for L2-normalised rows."""
    if embeddings.ndim != 2 or embeddings.shape[0] < 2:
        return np.zeros(0, dtype=np.float64)
    # Rows assumed L2-normalised → cosine = dot
    dots = np.sum(embeddings[:-1] * embeddings[1:], axis=1)
    dots = np.clip(dots, -1.0, 1.0)
    return (1.0 - dots).astype(np.float64)


def smooth_centered(series: np.ndarray, width: int = DEFAULT_SMOOTH_WIDTH) -> np.ndarray:
    if series.size == 0:
        return series.copy()
    w = int(width)
    if w < 1:
        w = 1
    if w % 2 == 0:
        w += 1
    radius = w // 2
    out = np.empty_like(series, dtype=np.float64)
    n = series.size
    for i in range(n):
        lo = max(0, i - radius)
        hi = min(n, i + radius + 1)
        out[i] = float(np.mean(series[lo:hi]))
    return out


def _mad(values: np.ndarray) -> float:
    if values.size == 0:
        return 0.0
    med = float(np.median(values))
    return float(np.median(np.abs(values - med)))


def decision_threshold(
    smoothed: np.ndarray,
    *,
    edge_exclude: int,
    thresholds: DetectorThresholds,
) -> float:
    n = smoothed.size
    if n == 0:
        return float(thresholds.absolute_floor)
    ee = max(0, int(edge_exclude))
    if n <= 2 * ee:
        core = smoothed
    else:
        core = smoothed[ee : n - ee]
    if core.size == 0:
        core = smoothed
    med = float(np.median(core))
    mad = _mad(core)
    if mad == 0.0:
        # Flat / MAD-zero: require absolute_floor only (no median inflation)
        return float(thresholds.absolute_floor)
    return float(max(thresholds.absolute_floor, med + thresholds.k_mad * mad))


def local_maxima_indices(
    smoothed: np.ndarray, *, edge_exclude: int
) -> list[int]:
    n = smoothed.size
    ee = max(0, int(edge_exclude))
    peaks: list[int] = []
    for i in range(1, n - 1):
        if i < ee or i >= n - ee:
            continue
        # strict vs previous, non-strict vs next
        if smoothed[i] > smoothed[i - 1] and smoothed[i] >= smoothed[i + 1]:
            peaks.append(i)
    return peaks


def local_prominence(smoothed: np.ndarray, i: int) -> float:
    return float(smoothed[i] - 0.5 * (smoothed[i - 1] + smoothed[i + 1]))


def normalized_strength(smoothed_i: float, threshold: float) -> float:
    denom = max(float(threshold), 1e-12)
    return round_metric((float(smoothed_i) - float(threshold)) / denom)


def centroid_ok(
    embeddings: np.ndarray,
    i: int,
    *,
    radius: int = DEFAULT_CENTROID_RADIUS,
    threshold: float = DEFAULT_CENTROID_THRESHOLD,
) -> bool:
    """
    Require left/right context centroids to differ by at least ``threshold``
    in cosine distance (reduces speaker-change / single-window FPs).
    """
    n = embeddings.shape[0]
    r = max(1, int(radius))
    # left windows ending at i inclusive? boundary is between i and i+1
    left = embeddings[max(0, i - r + 1) : i + 1]
    right = embeddings[i + 1 : min(n, i + 1 + r)]
    if left.size == 0 or right.size == 0:
        return False
    left_c = left.mean(axis=0)
    right_c = right.mean(axis=0)
    ln = np.linalg.norm(left_c)
    rn = np.linalg.norm(right_c)
    if ln < 1e-12 or rn < 1e-12:
        return False
    left_c = left_c / ln
    right_c = right_c / rn
    dist = 1.0 - float(np.dot(left_c, right_c))
    return round_metric(dist) >= round_metric(threshold)


def detect_peaks(
    embeddings: np.ndarray,
    windows: Sequence[TopicWindow],
    *,
    thresholds: DetectorThresholds,
    smooth_width: int = DEFAULT_SMOOTH_WIDTH,
    edge_exclude: int = DEFAULT_EDGE_EXCLUDE,
    centroid_radius: int = DEFAULT_CENTROID_RADIUS,
    centroid_threshold: float = DEFAULT_CENTROID_THRESHOLD,
    min_gap_windows: int = DEFAULT_MIN_GAP_WINDOWS,
    min_gap_seconds: float = DEFAULT_MIN_GAP_SECONDS,
    max_shifts: int = DEFAULT_MAX_SHIFTS,
) -> tuple[list[PeakCandidate], np.ndarray, np.ndarray, float]:
    """
    Return (candidates with accept flags), raw distances, smoothed, threshold used.

    Signal index i is the boundary between windows i and i+1.
    """
    raw = consecutive_distances(embeddings)
    smoothed = smooth_centered(raw, width=smooth_width)
    # Round smoothed for selection stability
    smoothed_r = np.array(
        [round_metric(x) for x in smoothed], dtype=np.float64
    )
    thr = decision_threshold(
        smoothed_r, edge_exclude=edge_exclude, thresholds=thresholds
    )
    thr = round_metric(thr)

    peaks = local_maxima_indices(smoothed_r, edge_exclude=edge_exclude)
    prelim: list[PeakCandidate] = []
    for i in peaks:
        prom = round_metric(local_prominence(smoothed_r, i))
        if prom <= 0 or prom < thresholds.min_prominence:
            continue
        sm = float(smoothed_r[i])
        if sm < thr:
            continue
        if not centroid_ok(
            embeddings,
            i,
            radius=centroid_radius,
            threshold=centroid_threshold,
        ):
            prelim.append(
                PeakCandidate(
                    distance_index=i,
                    raw_distance=round_metric(float(raw[i])),
                    smoothed_distance=sm,
                    local_prominence=prom,
                    decision_threshold=thr,
                    normalized_strength=normalized_strength(sm, thr),
                    time=float(windows[i + 1].start) if i + 1 < len(windows) else float(
                        windows[i].end
                    ),
                    accepted=False,
                    reject_reason="centroid",
                )
            )
            continue
        prelim.append(
            PeakCandidate(
                distance_index=i,
                raw_distance=round_metric(float(raw[i])),
                smoothed_distance=sm,
                local_prominence=prom,
                decision_threshold=thr,
                normalized_strength=normalized_strength(sm, thr),
                time=float(windows[i + 1].start) if i + 1 < len(windows) else float(
                    windows[i].end
                ),
                accepted=False,
                reject_reason=None,
            )
        )

    eligible = [p for p in prelim if p.reject_reason is None]
    eligible.sort(
        key=lambda p: (
            -p.local_prominence,
            -p.smoothed_distance,
            p.time,
            p.distance_index,
        )
    )

    accepted: list[PeakCandidate] = []
    for cand in eligible:
        if len(accepted) >= max_shifts:
            break
        ok = True
        for prev in accepted:
            gap_w = abs(cand.distance_index - prev.distance_index)
            gap_t = abs(cand.time - prev.time)
            need_w = min_gap_windows > 0
            need_t = min_gap_seconds > 0
            if need_w and need_t:
                if gap_w < min_gap_windows or gap_t < min_gap_seconds:
                    ok = False
                    break
            elif need_w:
                if gap_w < min_gap_windows:
                    ok = False
                    break
            elif need_t:
                if gap_t < min_gap_seconds:
                    ok = False
                    break
        if ok:
            accepted.append(
                PeakCandidate(
                    distance_index=cand.distance_index,
                    raw_distance=cand.raw_distance,
                    smoothed_distance=cand.smoothed_distance,
                    local_prominence=cand.local_prominence,
                    decision_threshold=cand.decision_threshold,
                    normalized_strength=cand.normalized_strength,
                    time=cand.time,
                    accepted=True,
                    reject_reason=None,
                )
            )

    accepted_ids = {p.distance_index for p in accepted}
    all_out: list[PeakCandidate] = []
    for p in prelim:
        if p.distance_index in accepted_ids:
            all_out.append(
                next(a for a in accepted if a.distance_index == p.distance_index)
            )
        else:
            reason = p.reject_reason or "min_gap_or_cap"
            all_out.append(
                PeakCandidate(
                    distance_index=p.distance_index,
                    raw_distance=p.raw_distance,
                    smoothed_distance=p.smoothed_distance,
                    local_prominence=p.local_prominence,
                    decision_threshold=p.decision_threshold,
                    normalized_strength=p.normalized_strength,
                    time=p.time,
                    accepted=False,
                    reject_reason=reason,
                )
            )
    all_out.sort(key=lambda p: p.distance_index)
    return all_out, raw, smoothed_r, thr


def reconcile_chunk_peaks(
    peaks_by_chunk: Sequence[Sequence[PeakCandidate]],
    *,
    min_gap_windows: int,
    min_gap_seconds: float,
    max_shifts: int,
) -> list[PeakCandidate]:
    """
    Merge accepted peaks across overlapping chunks.

    Duplicate distance_index: keep higher local_prominence, then earlier time.
    Then reapply min-gap and max_shifts globally.
    """
    best: dict[int, PeakCandidate] = {}
    for chunk_peaks in peaks_by_chunk:
        for p in chunk_peaks:
            if not p.accepted:
                continue
            prev = best.get(p.distance_index)
            if prev is None:
                best[p.distance_index] = p
                continue
            if (p.local_prominence, -p.time) > (
                prev.local_prominence,
                -prev.time,
            ):
                best[p.distance_index] = p

    merged = list(best.values())
    merged.sort(
        key=lambda p: (
            -p.local_prominence,
            -p.smoothed_distance,
            p.time,
            p.distance_index,
        )
    )
    accepted: list[PeakCandidate] = []
    for cand in merged:
        if len(accepted) >= max_shifts:
            break
        ok = True
        for prev in accepted:
            gap_w = abs(cand.distance_index - prev.distance_index)
            gap_t = abs(cand.time - prev.time)
            need_w = min_gap_windows > 0
            need_t = min_gap_seconds > 0
            if need_w and need_t:
                if gap_w < min_gap_windows or gap_t < min_gap_seconds:
                    ok = False
                    break
            elif need_w and gap_w < min_gap_windows:
                ok = False
                break
            elif need_t and gap_t < min_gap_seconds:
                ok = False
                break
        if ok:
            accepted.append(cand)
    accepted.sort(key=lambda p: p.time)
    return accepted
