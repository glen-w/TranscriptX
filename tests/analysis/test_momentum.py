from transcriptx.core.analysis.dynamics.momentum import MomentumAnalysis
from transcriptx.core.models.events import Event


def test_momentum_computes_timeseries_and_novelty():
    segments = [
        {"speaker": "Alice", "text": "We should ship tomorrow.", "start": 0.0, "end": 2.0},
        {"speaker": "Bob", "text": "I agree with shipping.", "start": 10.0, "end": 12.0},
        {"speaker": "Alice", "text": "Let's finalize the plan.", "start": 40.0, "end": 42.0},
    ]
    pauses_data = {
        "events": [
            Event(
                event_id="p1",
                kind="long_pause",
                time_start=2.0,
                time_end=5.0,
                speaker=None,
                segment_start_idx=0,
                segment_end_idx=1,
                severity=0.8,
            )
        ]
    }
    results = MomentumAnalysis().analyze(segments, pauses_data=pauses_data)
    assert len(results["timeseries"]) > 0
    assert results["timeseries"][0]["metrics"]["novelty"] >= 0.0
