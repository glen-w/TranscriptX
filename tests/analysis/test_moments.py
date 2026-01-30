from transcriptx.core.analysis.dynamics.moments import MomentsAnalysis
from transcriptx.core.models.events import Event


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
