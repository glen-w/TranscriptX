"""Offline unit tests for affect_tension chart output helpers."""

from __future__ import annotations

import math

import pytest

from transcriptx.core.analysis.affect_tension import output as at_out


_SPEAKER_IDS = {"Alice": 1, "Bob": 2, "SPEAKER_00": 100}


def _speaker_seg(
    speaker: str,
    *,
    start: float = 0.0,
    entropy: float | None = 1.0,
    volatility: float | None = 0.5,
    mismatch: bool | None = False,
    mismatch_type: str | None = None,
    trust_neutral: bool = False,
    start_unit: str | None = None,
    start_ms: float | None = None,
    start_s: float | None = None,
    start_time: float | None = None,
) -> dict:
    seg: dict = {
        "speaker": speaker,
        "speaker_db_id": _SPEAKER_IDS.get(speaker, abs(hash(speaker)) % 10000),
        "text": "hello",
        "start": start,
        "affect_mismatch_posneg": mismatch,
        "affect_trust_neutral": trust_neutral,
    }
    if entropy is not None:
        seg["emotion_entropy"] = entropy
    if volatility is not None:
        seg["emotion_volatility_proxy"] = volatility
    if mismatch_type is not None:
        seg["mismatch_type"] = mismatch_type
    if start_unit is not None:
        seg["start_unit"] = start_unit
    if start_ms is not None:
        seg["start_ms"] = start_ms
    if start_s is not None:
        seg["start_s"] = start_s
    if start_time is not None:
        seg["start_time"] = start_time
    return seg


@pytest.mark.unit
def test_safe_float_and_mean_helpers() -> None:
    assert at_out._safe_float("1.5") == 1.5
    assert at_out._safe_float("x") is None
    assert at_out._safe_float(math.nan) is None
    assert at_out._safe_float(math.inf) is None
    assert at_out._mean([None, 2.0, 4.0]) == 3.0
    assert at_out._mean([None, None]) is None


@pytest.mark.unit
def test_extract_start_seconds_branches() -> None:
    assert at_out._extract_start_seconds({"start_s": 12.5}) == 12.5
    assert at_out._extract_start_seconds({"start_ms": 2500}) == 2.5
    assert at_out._extract_start_seconds({"start_time": 3.0}) == 3.0
    assert at_out._extract_start_seconds({"start": 2000, "start_unit": "ms"}) == 2.0
    assert at_out._extract_start_seconds({"start": 4.0, "start_unit": "seconds"}) == 4.0
    assert at_out._extract_start_seconds({"start": 10}) == 10.0
    assert at_out._extract_start_seconds({"start": 1e5}) is None
    assert at_out._extract_start_seconds({}) is None
    assert at_out._extract_start_seconds({"start_ms": "bad"}) is None


@pytest.mark.unit
def test_build_derived_indices_charts_empty_segments() -> None:
    assert at_out.build_derived_indices_charts({}, [], "base") == []


@pytest.mark.unit
def test_build_derived_indices_charts_with_speakers_and_global() -> None:
    segments = [
        _speaker_seg("Alice", entropy=1.2, volatility=0.4, mismatch=True),
        _speaker_seg("Alice", entropy=0.8, volatility=0.6, mismatch=False, start=5),
        _speaker_seg("Bob", entropy=2.1, volatility=1.0, mismatch=True, start=10),
    ]
    derived = {
        "by_speaker": {
            "Alice": {
                "polite_tension_index": 0.3,
                "suppressed_conflict_score": 0.2,
                "institutional_tone_affect_delta": 0.1,
            },
            "Bob": {
                "polite_tension_index": 0.5,
                "suppressed_conflict_score": 0.4,
                "institutional_tone_affect_delta": 0.2,
            },
        },
        "global": {
            "polite_tension_index": 0.4,
            "suppressed_conflict_score": 0.3,
            "institutional_tone_affect_delta": 0.15,
        },
    }
    specs = at_out.build_derived_indices_charts(derived, segments, "call1")
    assert len(specs) >= 4
    names = {s.name for s in specs}
    assert "derived_polite_tension_index" in names
    assert "mismatch_rate" in names
    assert "avg_emotion_entropy" in names
    assert "avg_volatility_proxy" in names
    for spec in specs:
        assert "Global" in spec.categories or len(spec.categories) >= 1


@pytest.mark.unit
def test_build_derived_indices_skips_missing_speaker_derived() -> None:
    segments = [_speaker_seg("Alice"), _speaker_seg("Bob", start=1)]
    derived = {
        "by_speaker": {
            "Alice": {
                "polite_tension_index": 0.3,
                "suppressed_conflict_score": 0.2,
                "institutional_tone_affect_delta": 0.1,
            }
        },
        "global": {},
    }
    specs = at_out.build_derived_indices_charts(derived, segments, "base")
    polite = next(s for s in specs if s.name == "derived_polite_tension_index")
    assert polite.categories == ["Alice"]


@pytest.mark.unit
def test_build_dynamics_timeseries_combined_and_mismatch() -> None:
    segments = [
        _speaker_seg("Alice", start=0, entropy=1.0, volatility=0.5, mismatch=True),
        _speaker_seg("Alice", start=60, entropy=1.5, volatility=0.7, mismatch=False),
        _speaker_seg("Bob", start=120, entropy=0.5, volatility=0.2, mismatch=True),
    ]
    specs = at_out.build_dynamics_timeseries_charts(segments, "base")
    viz_ids = {s.viz_id for s in specs}
    assert any("entropy_volatility" in v or "entropy" in v for v in viz_ids)
    assert any("mismatch" in v for v in viz_ids)
    speaker_specs = [s for s in specs if s.scope == "speaker"]
    assert speaker_specs


@pytest.mark.unit
def test_build_dynamics_timeseries_entropy_only_and_empty() -> None:
    assert at_out.build_dynamics_timeseries_charts([], "base") == []
    segments = [
        _speaker_seg("Alice", start=0, entropy=1.0, volatility=None, mismatch=None),
        _speaker_seg("Alice", start=10, entropy=2.0, volatility=None, mismatch=None),
    ]
    specs = at_out.build_dynamics_timeseries_charts(segments, "base")
    assert any(s.name == "entropy_timeseries" for s in specs)

    vol_only = [
        _speaker_seg("Alice", start=0, entropy=None, volatility=0.5, mismatch=None),
        _speaker_seg("Alice", start=10, entropy=None, volatility=0.8, mismatch=None),
    ]
    specs_v = at_out.build_dynamics_timeseries_charts(vol_only, "base")
    assert any(s.name == "volatility_timeseries" for s in specs_v)


@pytest.mark.unit
def test_build_series_falls_back_to_index_when_start_unknown() -> None:
    xs, ys = at_out._build_series(
        [{"start": 1e5, "emotion_entropy": 1.0}],
        lambda seg: at_out._safe_float(seg.get("emotion_entropy")),
    )
    assert xs == [0.0]
    assert ys == [1.0]


@pytest.mark.unit
def test_heatmap_with_mismatch_types() -> None:
    segments = [
        _speaker_seg("Alice", mismatch_type="posneg", mismatch=True),
        _speaker_seg("Alice", mismatch_type="trust", mismatch=False, start=1),
        _speaker_seg("Bob", mismatch_type="posneg", mismatch=True, start=2),
    ]
    spec = at_out.build_tension_summary_heatmap({}, segments, "base")
    assert spec is not None
    assert spec.name == "mismatch_heatmap"
    assert "Global" in spec.y_labels
    assert "posneg" in spec.x_labels


@pytest.mark.unit
def test_heatmap_flag_categories_fallback() -> None:
    segments = [
        _speaker_seg(
            "Alice",
            entropy=2.5,
            mismatch=True,
            trust_neutral=True,
        ),
        _speaker_seg("Bob", entropy=0.5, mismatch=False, start=1),
    ]
    spec = at_out.build_tension_summary_heatmap({}, segments, "base")
    assert spec is not None
    assert "posneg_mismatch" in spec.x_labels


@pytest.mark.unit
def test_heatmap_metrics_fallback_when_no_flags() -> None:
    segments = [
        _speaker_seg("Alice", entropy=0.5, volatility=0.2, mismatch=False),
        _speaker_seg("Bob", entropy=0.4, volatility=0.1, mismatch=False, start=1),
    ]
    derived = {
        "by_speaker": {
            "Alice": {
                "polite_tension_index": 0.1,
                "suppressed_conflict_score": 0.2,
                "institutional_tone_affect_delta": 0.3,
            },
            "Bob": {
                "polite_tension_index": 0.15,
                "suppressed_conflict_score": 0.25,
                "institutional_tone_affect_delta": 0.35,
            },
        },
        "global": {
            "polite_tension_index": 0.12,
            "suppressed_conflict_score": 0.22,
            "institutional_tone_affect_delta": 0.32,
        },
    }
    spec = at_out.build_tension_summary_heatmap(derived, segments, "base")
    assert spec is not None
    assert spec.name == "metrics_heatmap"
    assert "Polite Tension" in spec.x_labels


@pytest.mark.unit
def test_heatmap_returns_none_for_empty_or_incomplete() -> None:
    assert at_out.build_tension_summary_heatmap({}, [], "base") is None
    segments = [_speaker_seg("Alice", entropy=0.1, volatility=0.1, mismatch=False)]
    # Missing derived for metrics path and no positive flag rates:
    # high entropy path needs mismatch True; here all flags false => possibly None
    derived = {"by_speaker": {}, "global": {}}
    # With mismatch False and low entropy, flag heatmap needs any(val > 0)
    # All zeros → fall through to metrics → incomplete → None
    assert at_out.build_tension_summary_heatmap(derived, segments, "base") is None


@pytest.mark.unit
def test_rate_and_group_segments() -> None:
    assert at_out._rate([], lambda s: True) is None
    segs = [{"x": 1}, {"x": 0}, {"x": 1}]
    assert at_out._rate(segs, lambda s: s.get("x") == 1) == pytest.approx(2 / 3)

    speakers, grouped = at_out._group_segments(
        [
            _speaker_seg("Alice"),
            _speaker_seg("Bob", start=1),
            _speaker_seg("SPEAKER_00", start=2),
        ],
        max_speakers=1,
    )
    assert speakers == ["Alice"] or speakers == ["Bob"]
    assert len(speakers) == 1
    assert set(grouped.keys()) == set(speakers)
