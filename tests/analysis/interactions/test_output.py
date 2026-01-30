"""Tests for interactions output helpers."""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.analysis.interactions.events import InteractionEvent
from transcriptx.core.analysis.interactions.output import save_interaction_events
from transcriptx.core.utils.output_standards import create_standard_output_structure


def test_save_interaction_events_writes_json_and_csv(tmp_path: Path) -> None:
    output_structure = create_standard_output_structure(str(tmp_path), "interactions")
    interactions = [
        InteractionEvent(
            timestamp=1.0,
            speaker_a="A",
            speaker_b="B",
            interaction_type="response",
            speaker_a_text="hello",
            speaker_b_text="hi",
            gap_before=0.2,
            overlap=0.0,
            speaker_a_start=0.0,
            speaker_a_end=1.0,
            speaker_b_start=1.2,
            speaker_b_end=2.0,
        )
    ]
    save_interaction_events(
        interactions, output_structure=output_structure, base_name="sample"
    )
    json_path = (
        output_structure.global_data_dir / "sample_interaction_events.json"
    )
    csv_path = (
        output_structure.global_data_dir / "sample_interaction_events.csv"
    )
    assert json_path.exists()
    assert csv_path.exists()
