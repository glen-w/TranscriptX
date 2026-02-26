"""Tests for event JSON enrichment."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.core.io.events_io import save_events_json
from transcriptx.core.models.events import Event


def test_save_events_json_adds_anchor_and_segment_ref(tmp_path: Path) -> None:
    events = [
        Event(
            event_id="evt-1",
            kind="pause",
            time_start=12.0,
            time_end=14.0,
            speaker="Ada",
            segment_start_idx=3,
            segment_end_idx=5,
            severity=0.6,
            score=0.8,
        ),
        Event(
            event_id="evt-2",
            kind="pause",
            time_start=20.0,
            time_end=21.0,
            speaker=None,
            segment_start_idx=None,
            segment_end_idx=None,
            severity=0.2,
            score=None,
        ),
    ]
    output_path = save_events_json(
        events,
        output_structure=tmp_path,
        filename="events.json",
        output_dir=tmp_path,
    )
    payload = json.loads(Path(output_path).read_text(encoding="utf-8"))
    assert payload[0]["segment_ref"]["segment_indexes"] == [3, 5]
    assert payload[0]["anchor"] == "0:12-0:14 | Ada | seg#3-5"
    assert payload[0]["status"] == "ok"
    assert "segment_ref" not in payload[1]
    assert "anchor" not in payload[1]


from types import SimpleNamespace

from transcriptx.core.io.events_io import load_events_json


def test_save_load_events_json_sorted(tmp_path):
    output_structure = SimpleNamespace(global_data_dir=tmp_path)
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
    path = save_events_json(events, output_structure, "events.json")
    loaded = load_events_json(path)
    assert [event.event_id for event in loaded] == ["a", "b"]
