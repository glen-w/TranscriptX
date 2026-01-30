"""Tests for interaction event invariants."""

from __future__ import annotations

from transcriptx.core.analysis.interactions.events import InteractionEvent


def test_event_time_consistency() -> None:
    event = InteractionEvent(
        timestamp=2.0,
        speaker_a="A",
        speaker_b="B",
        interaction_type="response",
        speaker_a_text="hello",
        speaker_b_text="hi",
        gap_before=0.2,
        overlap=0.0,
        speaker_a_start=0.0,
        speaker_a_end=1.0,
        speaker_b_start=2.0,
        speaker_b_end=3.0,
    )
    assert event.speaker_a_start <= event.speaker_a_end
    assert event.speaker_b_start <= event.speaker_b_end
    assert event.timestamp == event.speaker_b_start
