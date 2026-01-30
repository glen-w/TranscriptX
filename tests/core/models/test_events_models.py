from transcriptx.core.models.events import Event, generate_event_id, sort_events_deterministically


def test_generate_event_id_deterministic():
    event_id_1 = generate_event_id(
        transcript_hash="hash123",
        kind="long_pause",
        segment_start_idx=1,
        segment_end_idx=2,
        time_start=1.234,
        time_end=3.456,
    )
    event_id_2 = generate_event_id(
        transcript_hash="hash123",
        kind="long_pause",
        segment_start_idx=1,
        segment_end_idx=2,
        time_start=1.29,
        time_end=3.45,
    )
    assert event_id_1 == event_id_2


def test_sort_events_deterministically():
    events = [
        Event(
            event_id="b",
            kind="echo",
            time_start=5.0,
            time_end=5.5,
            speaker=None,
            segment_start_idx=2,
            segment_end_idx=3,
            severity=0.5,
        ),
        Event(
            event_id="a",
            kind="long_pause",
            time_start=2.0,
            time_end=2.5,
            speaker=None,
            segment_start_idx=0,
            segment_end_idx=1,
            severity=0.9,
        ),
    ]
    sorted_events = sort_events_deterministically(events)
    assert [e.event_id for e in sorted_events] == ["a", "b"]
