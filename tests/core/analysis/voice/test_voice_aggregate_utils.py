from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from transcriptx.core.analysis.voice import aggregate as agg


def test_robust_stats_empty_and_nonempty() -> None:
    empty = agg.robust_stats(np.array([]))
    assert empty == {"median": 0.0, "iqr": 0.0, "sigma": 1.0}

    vals = agg.robust_stats(np.array([1.0, 2.0, 3.0]))
    assert vals["median"] == pytest.approx(2.0)
    assert vals["iqr"] > 0
    assert vals["sigma"] > 0


def test_robust_z_handles_none_nan_and_small_sigma() -> None:
    assert agg.robust_z(None, median=0.0, sigma=1.0) == 0.0
    assert agg.robust_z(float("nan"), median=0.0, sigma=1.0) == 0.0
    assert agg.robust_z(2.0, median=1.0, sigma=0.0) == pytest.approx(1.0)


def test_compute_arousal_and_mismatch_score_paths() -> None:
    arousal = agg.compute_arousal_raw(
        rms_db=2.0,
        f0_range_semitones=1.0,
        speech_rate_wps=3.0,
        stats_energy={"median": 1.0, "sigma": 1.0},
        stats_pitch_range={"median": 1.0, "sigma": 1.0},
        stats_rate={"median": 1.0, "sigma": 1.0},
    )
    assert arousal > 0
    with_val = agg.compute_mismatch_score(
        vader_compound=0.8, arousal_raw=arousal, valence_raw=-1.5
    )
    no_val = agg.compute_mismatch_score(
        vader_compound=0.8, arousal_raw=arousal, valence_raw=None
    )
    assert 0 <= with_val <= 1
    assert 0 <= no_val <= 1


def test_compute_valence_proxy_requires_stats_and_fields() -> None:
    assert (
        agg.compute_valence_proxy(
            eg=None,
            stats_hnr={},
            stats_jitter={},
            stats_shimmer={},
            stats_alpha={},
        )
        is None
    )
    out = agg.compute_valence_proxy(
        eg={"hnr_db": 2.0, "jitter": 0.1, "shimmer_db": 0.2, "alpha_ratio": 1.0},
        stats_hnr={"median": 1.0, "sigma": 1.0},
        stats_jitter={"median": 0.0, "sigma": 1.0},
        stats_shimmer={"median": 0.0, "sigma": 1.0},
        stats_alpha={"median": 0.0, "sigma": 1.0},
    )
    assert out is not None


def test_compute_tension_curve_empty_and_smoothed() -> None:
    assert (
        agg.compute_tension_curve(df=None, bin_seconds=1.0, smoothing_alpha=0.5) == []
    )
    df = pd.DataFrame(
        [
            {"speaker": "A", "start_s": 0.0, "end_s": 1.0, "arousal_raw": 1.0},
            {"speaker": "A", "start_s": 1.0, "end_s": 2.0, "arousal_raw": 2.0},
        ]
    )
    rows = agg.compute_tension_curve(
        df=df, bin_seconds=1.0, smoothing_alpha=0.5, include_speakers={"A"}
    )
    assert len(rows) >= 2
    assert rows[0]["segments_n"] >= 1
    assert "tension_smooth" in rows[0]


def test_compute_speaker_fingerprints_and_drift_named_only() -> None:
    df = pd.DataFrame(
        [
            {
                "speaker": "Alice",
                "segment_id": "s1",
                "start_s": 0.0,
                "end_s": 1.0,
                "rms_db": 1.0,
                "f0_range_semitones": 1.0,
                "speech_rate_wps": 1.0,
            },
            {
                "speaker": "Alice",
                "segment_id": "s2",
                "start_s": 1.0,
                "end_s": 2.0,
                "rms_db": 5.0,
                "f0_range_semitones": 4.0,
                "speech_rate_wps": 4.0,
            },
            {
                "speaker": "SPEAKER_01",
                "segment_id": "s3",
                "start_s": 2.0,
                "end_s": 3.0,
                "rms_db": 1.0,
                "f0_range_semitones": 1.0,
                "speech_rate_wps": 1.0,
            },
        ]
    )
    fingerprints, drift = agg.compute_speaker_fingerprints_and_drift(
        df=df, top_k=3, drift_threshold=0.1
    )
    assert "Alice" in fingerprints
    assert "Alice" in drift
    assert "SPEAKER_01" not in fingerprints
