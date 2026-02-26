from __future__ import annotations

from typing import Any, Tuple

import numpy as np

from transcriptx.utils.text_utils import is_named_speaker  # type: ignore[import-untyped]


EPS = 1e-9


def robust_stats(values: np.ndarray) -> dict[str, float]:
    vals = np.asarray(values, dtype=np.float64)
    vals = vals[np.isfinite(vals)]
    if vals.size == 0:
        return {"median": 0.0, "iqr": 0.0, "sigma": 1.0}
    med = float(np.median(vals))
    q25 = float(np.percentile(vals, 25))
    q75 = float(np.percentile(vals, 75))
    iqr = float(q75 - q25)
    sigma = max(iqr / 1.349, EPS)
    return {"median": med, "iqr": iqr, "sigma": float(sigma)}


def robust_z(x: float | None, *, median: float, sigma: float) -> float:
    if x is None or not np.isfinite(x):
        return 0.0
    denom = sigma if sigma and sigma > EPS else 1.0
    return float((float(x) - float(median)) / denom)


def _sigmoid(x: float) -> float:
    return float(1.0 / (1.0 + np.exp(-x)))


def _soft_sign(x: float) -> float:
    return float(np.tanh(2.0 * x))


def compute_arousal_raw(
    *,
    rms_db: float | None,
    f0_range_semitones: float | None,
    speech_rate_wps: float | None,
    stats_energy: dict[str, float],
    stats_pitch_range: dict[str, float],
    stats_rate: dict[str, float],
) -> float:
    z_energy = robust_z(
        rms_db, median=stats_energy["median"], sigma=stats_energy["sigma"]
    )
    z_pitch = robust_z(
        f0_range_semitones,
        median=stats_pitch_range["median"],
        sigma=stats_pitch_range["sigma"],
    )
    z_rate = robust_z(
        speech_rate_wps, median=stats_rate["median"], sigma=stats_rate["sigma"]
    )
    return float(0.50 * z_energy + 0.30 * z_pitch + 0.20 * z_rate)


def compute_valence_proxy(
    *,
    eg: dict[str, float] | None,
    stats_hnr: dict[str, float] | None,
    stats_jitter: dict[str, float] | None,
    stats_shimmer: dict[str, float] | None,
    stats_alpha: dict[str, float] | None,
) -> float | None:
    if not eg:
        return None
    if not (stats_hnr and stats_jitter and stats_shimmer and stats_alpha):
        return None
    hnr = eg.get("hnr_db")
    jitter = eg.get("jitter")
    shimmer = eg.get("shimmer_db")
    alpha = eg.get("alpha_ratio")
    if hnr is None or jitter is None or shimmer is None or alpha is None:
        return None
    hnr_z = robust_z(hnr, median=stats_hnr["median"], sigma=stats_hnr["sigma"])
    jitter_z = robust_z(
        jitter, median=stats_jitter["median"], sigma=stats_jitter["sigma"]
    )
    shimmer_z = robust_z(
        shimmer, median=stats_shimmer["median"], sigma=stats_shimmer["sigma"]
    )
    alpha_z = robust_z(alpha, median=stats_alpha["median"], sigma=stats_alpha["sigma"])
    return float(0.45 * hnr_z - 0.25 * jitter_z - 0.25 * shimmer_z + 0.05 * alpha_z)


def compute_mismatch_score(
    *,
    vader_compound: float,
    arousal_raw: float,
    valence_raw: float | None,
) -> float:
    t = float(vader_compound)
    a = float(arousal_raw)
    if valence_raw is not None:
        v = float(np.tanh(valence_raw))
        disagreement = 0.5 * (1.0 - _soft_sign(t) * _soft_sign(v))
        return float(abs(t) * disagreement * (0.6 + 0.4 * _sigmoid(abs(a))))

    flat_affect = abs(t) * _sigmoid(-abs(a))
    heated_neutral = (1.0 - abs(t)) * _sigmoid(abs(a) - 1.0)
    return float(max(flat_affect, heated_neutral))


def compute_tension_curve(
    *,
    df: Any,
    bin_seconds: float,
    smoothing_alpha: float,
    include_speakers: set[str] | None = None,
) -> list[dict[str, Any]]:
    # df is a pandas DataFrame with at least start_s/end_s/arousal_raw
    if df is None or df.empty:
        return []

    work = df.copy()
    if include_speakers is not None:
        work = work[work["speaker"].isin(list(include_speakers))]
    if work.empty:
        return []

    start0 = float(work["start_s"].min())
    end0 = float(work["end_s"].max())
    if not np.isfinite(start0) or not np.isfinite(end0) or end0 <= start0:
        return []

    bins = np.arange(start0, end0 + bin_seconds, bin_seconds)
    rows: list[dict[str, Any]] = []
    prev = None
    for b0 in bins[:-1]:
        b1 = b0 + bin_seconds
        overlaps = work[(work["start_s"] < b1) & (work["end_s"] > b0)]
        if overlaps.empty:
            tension_raw = 0.0
            ar_med = 0.0
            ar_p90 = 0.0
            voiced = None
            n = 0
        else:
            ar = overlaps["arousal_raw"].astype(float).to_numpy()
            ar = ar[np.isfinite(ar)]
            if ar.size == 0:
                ar_med = 0.0
                ar_p90 = 0.0
            else:
                ar_med = float(np.median(ar))
                ar_p90 = float(np.percentile(ar, 90))
            tension_raw = float(0.7 * ar_p90 + 0.3 * ar_med)
            vr = overlaps.get("voiced_ratio")
            voiced = (
                float(np.nanmean(vr.astype(float).to_numpy()))
                if vr is not None
                else None
            )
            n = int(len(overlaps))

        if prev is None:
            smooth = tension_raw
        else:
            smooth = float(
                smoothing_alpha * tension_raw + (1.0 - smoothing_alpha) * prev
            )
        prev = smooth
        rows.append(
            {
                "bin_start_s": float(b0),
                "bin_end_s": float(b1),
                "tension_raw": float(tension_raw),
                "tension_smooth": float(smooth),
                "arousal_median": float(ar_med),
                "arousal_p90": float(ar_p90),
                "voiced_ratio_mean": voiced,
                "segments_n": n,
            }
        )
    return rows


def compute_speaker_fingerprints_and_drift(
    *,
    df: Any,
    top_k: int,
    drift_threshold: float,
) -> Tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    """
    Returns (fingerprints, drift_moments) for named speakers only.
    """
    if df is None or df.empty:
        return ({}, {})

    fingerprints: dict[str, Any] = {}
    drift: dict[str, list[dict[str, Any]]] = {}

    for speaker, group in df.groupby("speaker"):
        if not speaker or not is_named_speaker(str(speaker)):
            continue
        g = group.copy()
        stats_energy = robust_stats(g["rms_db"].astype(float).to_numpy())
        stats_pitch = robust_stats(g["f0_range_semitones"].astype(float).to_numpy())
        stats_rate = robust_stats(g["speech_rate_wps"].astype(float).to_numpy())

        fingerprints[str(speaker)] = {
            "speaker": str(speaker),
            "baseline": {
                "rms_db": stats_energy,
                "f0_range_semitones": stats_pitch,
                "speech_rate_wps": stats_rate,
            },
            "n_segments": int(len(g)),
        }

        # Compute drift score per segment (max abs z)
        z_energy = g["rms_db"].apply(
            lambda x: abs(
                robust_z(x, median=stats_energy["median"], sigma=stats_energy["sigma"])
            )
        )
        z_pitch = g["f0_range_semitones"].apply(
            lambda x: abs(
                robust_z(x, median=stats_pitch["median"], sigma=stats_pitch["sigma"])
            )
        )
        z_rate = g["speech_rate_wps"].apply(
            lambda x: abs(
                robust_z(x, median=stats_rate["median"], sigma=stats_rate["sigma"])
            )
        )
        drift_score = np.maximum.reduce(
            [z_energy.to_numpy(), z_pitch.to_numpy(), z_rate.to_numpy()]
        )
        g = g.assign(drift_score=drift_score)
        candidates = g[g["drift_score"] >= float(drift_threshold)]
        candidates = candidates.sort_values("drift_score", ascending=False).head(
            int(top_k)
        )
        moments: list[dict[str, Any]] = []
        for rank, (_, row) in enumerate(candidates.iterrows(), start=1):
            moments.append(
                {
                    "rank": rank,
                    "segment_id": row.get("segment_id"),
                    "speaker": str(speaker),
                    "start_s": float(row.get("start_s", 0.0)),
                    "end_s": float(row.get("end_s", 0.0)),
                    "drift_score": float(row.get("drift_score", 0.0)),
                    "rms_db": row.get("rms_db"),
                    "f0_range_semitones": row.get("f0_range_semitones"),
                    "speech_rate_wps": row.get("speech_rate_wps"),
                }
            )
        drift[str(speaker)] = moments

    return fingerprints, drift
