from transcriptx.core.analysis.dynamics.moments import (
    MomentsAnalysis,
    _overlapping_segments,
)
from transcriptx.core.models.events import Event
from transcriptx.core.viz.specs import ScatterSpec


def test_moments_ranked_output():
    pauses_data = {
        "events": [
            Event(
                event_id="p1",
                kind="long_pause",
                time_start=5.0,
                time_end=7.0,
                speaker=None,
                segment_start_idx=1,
                segment_end_idx=2,
                severity=0.9,
            )
        ]
    }
    echoes_data = {
        "events": [
            Event(
                event_id="e1",
                kind="echo_burst",
                time_start=10.0,
                time_end=12.0,
                speaker=None,
                segment_start_idx=3,
                segment_end_idx=4,
                severity=0.7,
            )
        ]
    }
    momentum_data = {
        "events": [
            Event(
                event_id="m1",
                kind="momentum_cliff",
                time_start=15.0,
                time_end=16.0,
                speaker=None,
                segment_start_idx=5,
                segment_end_idx=6,
                severity=0.6,
            )
        ]
    }
    results = MomentsAnalysis().analyze(
        segments=[{"start": 0.0, "end": 20.0, "speaker": "Alice", "text": "hi"}],
        pauses_data=pauses_data,
        echoes_data=echoes_data,
        momentum_data=momentum_data,
    )
    assert results["events"]
    assert results["moments"][0]["rank"] == 1
    # New fields should be present
    assert "score_breakdown" in results["moments"][0]
    assert "segment_count" in results["moments"][0]


def test_build_timeline_spec_sorted_by_time():
    """Chart spec must be built from moments sorted by time_start, not score rank."""
    analysis = MomentsAnalysis()
    # Moments in score rank order (high score first) - not time order
    moments_rank_order = [
        {"time_start": 100.0, "time_end": 110.0, "score": 2.0},
        {"time_start": 10.0, "time_end": 20.0, "score": 1.5},
        {"time_start": 50.0, "time_end": 55.0, "score": 1.0},
    ]
    spec = analysis._build_timeline_spec(moments_rank_order)
    assert spec is not None
    assert isinstance(spec, ScatterSpec)
    series_list = spec.get_series()
    assert len(series_list) == 1
    x_vals = list(series_list[0].x)
    # Spec internally sorts by time_start, so x should be chronological
    assert x_vals == sorted(x_vals), "Timeline x values must be sorted by time_start"
    assert x_vals == [
        10.0 / 60.0,
        50.0 / 60.0,
        100.0 / 60.0,
    ]  # time_axis_display -> minutes
    assert spec.mode == "markers"


def test_build_timeline_spec_duration_as_marker_size():
    """When duration varies, marker size should reflect it (longer = larger)."""
    analysis = MomentsAnalysis()
    moments = [
        {"time_start": 0.0, "time_end": 10.0, "score": 1.0},  # duration 10
        {"time_start": 20.0, "time_end": 25.0, "score": 1.0},  # duration 5
    ]
    spec = analysis._build_timeline_spec(moments)
    assert spec is not None
    series_list = spec.get_series()
    assert len(series_list) == 1
    marker = series_list[0].marker
    assert marker is not None
    sizes = marker.get("size")
    assert sizes is not None
    assert len(sizes) == 2
    # First moment has longer duration -> larger size
    assert sizes[0] > sizes[1]


def test_build_timeline_spec_empty_returns_none():
    assert MomentsAnalysis()._build_timeline_spec([]) is None


def test_overlapping_segments():
    segments = [
        {"start": 0.0, "end": 5.0, "speaker": "A", "text": "one"},
        {"start": 4.0, "end": 10.0, "speaker": "B", "text": "two"},
        {"start": 12.0, "end": 18.0, "speaker": "A", "text": "three"},
    ]
    # Overlap [3, 8]: segments 0 and 1 (indices 0, 1)
    out = _overlapping_segments(segments, 3.0, 8.0)
    assert len(out) == 2
    idxs = sorted(i for i, _ in out)
    assert idxs == [0, 1]
    # Overlap [11, 14]: only segment 2
    out2 = _overlapping_segments(segments, 11.0, 14.0)
    assert len(out2) == 1
    assert out2[0][0] == 2
    # No overlap
    assert _overlapping_segments(segments, 20.0, 25.0) == []


def test_enrichment_and_score_breakdown():
    """Enrichment uses transcript overlap; score_breakdown total = base + bonuses."""
    segments = [
        {"start": 0.0, "end": 30.0, "speaker": "Alice", "text": "Hello"},
        {"start": 32.0, "end": 50.0, "speaker": "Bob", "text": "Hi there"},
    ]
    pauses_data = {
        "events": [
            Event(
                event_id="p1",
                kind="long_pause",
                time_start=5.0,
                time_end=8.0,
                speaker=None,
                segment_start_idx=None,
                segment_end_idx=None,
                severity=1.0,
            )
        ]
    }
    echoes_data = {
        "events": [
            Event(
                event_id="e1",
                kind="echo_burst",
                time_start=10.0,
                time_end=14.0,
                speaker=None,
                segment_start_idx=None,
                segment_end_idx=None,
                severity=0.8,
            )
        ]
    }
    results = MomentsAnalysis().analyze(
        segments=segments,
        pauses_data=pauses_data,
        echoes_data=echoes_data,
        momentum_data=None,
    )
    moments = results["moments"]
    assert len(moments) >= 1
    m = moments[0]
    # Transcript-derived segment_refs and speakers (span 5–14 overlaps seg 0)
    assert "segment_refs" in m
    assert "speakers" in m
    assert "score_breakdown" in m
    b = m["score_breakdown"]
    assert b["score_total"] == (
        b["score_base"] + b["score_diversity_bonus"] + b["score_multi_speaker_bonus"]
    )
    assert b["score_base"] == sum(b["per_kind_contributions"].values())
    assert "sources_included" in b
    assert b["event_count"] >= 1
