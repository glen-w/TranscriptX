"""Unit tests for topic_shift detector geometry and segments."""

from __future__ import annotations

import numpy as np

from transcriptx.core.analysis.topic_shift.detector import (
    DetectorThresholds,
    consecutive_distances,
    detect_peaks,
    reconcile_chunk_peaks,
    round_metric,
    smooth_centered,
)
from transcriptx.core.analysis.topic_shift.segments import canonicalise_segments
from transcriptx.core.analysis.topic_shift.windowing import (
    TopicWindow,
    build_rolling_windows,
    partition_overlapping_chunks,
)


def _windows(n: int) -> list[TopicWindow]:
    out = []
    for i in range(n):
        out.append(
            TopicWindow(
                window_id=f"window_{i}",
                global_index=i,
                segment_indexes=(i,),
                canonical_positions=(i,),
                start=float(i * 10),
                end=float(i * 10 + 9),
                raw_text=f"text {i}",
                lexical_text=f"text {i}",
            )
        )
    return out


def test_consecutive_distances_orthogonal():
    emb = np.array([[1.0, 0.0], [0.0, 1.0], [0.0, 1.0]], dtype=np.float64)
    d = consecutive_distances(emb)
    assert d.shape == (2,)
    assert abs(d[0] - 1.0) < 1e-9
    assert abs(d[1] - 0.0) < 1e-9


def test_smooth_centered_odd_width():
    series = np.array([0.0, 1.0, 0.0, 1.0, 0.0], dtype=np.float64)
    sm = smooth_centered(series, width=3)
    assert sm.shape == series.shape
    assert abs(sm[1] - (0 + 1 + 0) / 3) < 1e-9


def test_detect_clear_shift_peak():
    # Build embeddings: first half one direction, second half orthogonal
    n = 12
    emb = np.zeros((n, 2), dtype=np.float64)
    emb[:6, 0] = 1.0
    emb[6:, 1] = 1.0
    windows = _windows(n)
    thr = DetectorThresholds(k_mad=1.0, absolute_floor=0.05, min_prominence=0.01)
    peaks, raw, smoothed, threshold = detect_peaks(
        emb,
        windows,
        thresholds=thr,
        edge_exclude=1,
        centroid_radius=2,
        centroid_threshold=0.05,
        min_gap_windows=1,
        min_gap_seconds=0.0,
        max_shifts=5,
    )
    accepted = [p for p in peaks if p.accepted]
    assert accepted, f"expected peak; raw={raw} smoothed={smoothed} thr={threshold}"
    # Smoothing can shift the local max by one window; require near the topic cut (5).
    assert any(abs(p.distance_index - 5) <= 1 for p in accepted)


def test_reconcile_prefers_higher_prominence():
    from transcriptx.core.analysis.topic_shift.detector import PeakCandidate

    a = PeakCandidate(
        distance_index=3,
        raw_distance=0.5,
        smoothed_distance=0.5,
        local_prominence=0.1,
        decision_threshold=0.2,
        normalized_strength=1.0,
        time=30.0,
        accepted=True,
    )
    b = PeakCandidate(
        distance_index=3,
        raw_distance=0.6,
        smoothed_distance=0.6,
        local_prominence=0.4,
        decision_threshold=0.2,
        normalized_strength=2.0,
        time=30.0,
        accepted=True,
    )
    out = reconcile_chunk_peaks(
        [[a], [b]],
        min_gap_windows=0,
        min_gap_seconds=0.0,
        max_shifts=5,
    )
    assert len(out) == 1
    assert out[0].local_prominence == 0.4


def test_canonicalise_retains_source_index_after_sort():
    segs = [
        {"start": 10.0, "end": 11.0, "text": "second utterance here"},
        {"start": 1.0, "end": 2.0, "text": "first utterance here"},
        {"start": 5.0, "end": 4.0, "text": "reversed bad"},  # skipped
    ]
    result = canonicalise_segments(segs, min_text_chars=5)
    assert result.analytical_status is None
    assert len(result.segments) == 2
    assert result.segments[0].source_index == 1
    assert result.segments[1].source_index == 0
    assert result.skipped_invalid == 1


def test_speaker_rename_stable_identity_via_span_builder():
    from transcriptx.core.analysis.topic_shift.spans import transcript_identity_for_segments

    a = [{"start": 0.0, "end": 1.0, "text": "hello world", "speaker": "A"}]
    b = [{"start": 0.0, "end": 1.0, "text": "hello world", "speaker": "Renamed"}]
    assert transcript_identity_for_segments(a) == transcript_identity_for_segments(b)


def test_chunk_coverage_complete():
    segs = [
        {
            "start": float(i),
            "end": float(i) + 0.8,
            "text": f"segment number {i} with enough text",
        }
        for i in range(30)
    ]
    canon = canonicalise_segments(segs)
    windows = build_rolling_windows(canon.segments, window_size=5, stride=2)
    chunks, coverage = partition_overlapping_chunks(
        windows, max_windows_per_chunk=8, overlap_windows=2
    )
    assert coverage.complete
    assert coverage.n_chunks >= 2
    assert round_metric(1.23456789) == 1.234568


def test_module_import_and_registry():
    from transcriptx.core.pipeline.module_registry_specs import MODULE_CLASS_MAP
    from transcriptx.core.pipeline.module_specs import MODULE_REGISTRY_ORDER

    assert "topic_shift" in MODULE_CLASS_MAP
    assert "topic_shift" in MODULE_REGISTRY_ORDER
    assert MODULE_REGISTRY_ORDER.index("topic_shift") < MODULE_REGISTRY_ORDER.index(
        "moments"
    )
