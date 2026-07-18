"""Tests for interactions output helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.core.analysis.interactions.events import InteractionEvent
from transcriptx.core.analysis.interactions.output import (
    analyze_interactions,
    save_interaction_events,
    save_interaction_matrix_data,
)
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
    json_path = output_structure.global_data_dir / "sample_interaction_events.json"
    csv_path = output_structure.global_data_dir / "sample_interaction_events.csv"
    assert json_path.exists()
    assert csv_path.exists()


def test_save_interaction_events_skips_rows_with_missing_speakers(
    tmp_path: Path,
) -> None:
    output_structure = create_standard_output_structure(str(tmp_path), "interactions")
    interactions = [
        InteractionEvent(
            timestamp=1.0,
            speaker_a="",
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
    assert not (
        output_structure.global_data_dir / "sample_interaction_events.json"
    ).exists()
    assert not (
        output_structure.global_data_dir / "sample_interaction_events.csv"
    ).exists()


def test_save_interaction_matrix_data_returns_early_for_empty_matrix(
    tmp_path: Path,
) -> None:
    output_structure = create_standard_output_structure(str(tmp_path), "interactions")
    save_interaction_matrix_data({"interaction_matrix": {}}, output_structure, "sample")
    assert list(output_structure.global_data_dir.glob("*matrix*.csv")) == []


def test_analyze_interactions_generates_visualizations_when_events_exist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    event = InteractionEvent(
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

    class _Analyzer:
        def __init__(self, **_kwargs):
            pass

        def detect_interactions(self, _segments):
            return [event]

        def analyze_interactions(self, _interactions, _speaker_map):
            return {
                "interruption_initiated": {"A": 0, "B": 0},
                "responses_initiated": {"A": 1, "B": 0},
                "interruption_received": {"A": 0, "B": 0},
                "responses_received": {"A": 0, "B": 1},
                "net_interruption_balance": {"A": 0, "B": 0},
                "net_response_balance": {"A": 1, "B": -1},
                "total_interactions": {"A": 1, "B": 1},
                "dominance_scores": {"A": 1, "B": 0},
                "interaction_matrix": {
                    "A": {"B": {"responses": 1, "interruptions": 0}}
                },
                "total_interactions_count": 1,
                "unique_speakers": 2,
                "interaction_types": {"responses": 1},
            }

    monkeypatch.setattr(
        "transcriptx.core.analysis.interactions.output.SpeakerInteractionAnalyzer",
        _Analyzer,
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.interactions.output.get_config",
        lambda: type(
            "Cfg",
            (),
            {
                "analysis": type(
                    "A",
                    (),
                    {
                        "interaction_overlap_threshold": 0.1,
                        "interaction_min_gap": 0.1,
                        "interaction_min_segment_length": 0.1,
                        "interaction_response_threshold": 0.2,
                        "interaction_include_responses": True,
                        "interaction_include_overlaps": True,
                    },
                )()
            },
        )(),
    )

    calls: list[str] = []

    def _mark(name):
        def _fn(*_args, **_kwargs):
            calls.append(name)

        return _fn

    monkeypatch.setattr(
        "transcriptx.core.analysis.interactions.output.create_combined_timeline",
        _mark("timeline"),
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.interactions.output.create_interaction_network",
        _mark("network"),
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.interactions.output.create_interaction_network_graph",
        _mark("network_graph"),
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.interactions.output.create_interaction_heatmap",
        _mark("heatmap"),
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.interactions.output.create_dominance_analysis",
        _mark("dominance"),
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.interactions.output.create_speaker_timeline_charts",
        _mark("speaker_timeline"),
    )

    result = analyze_interactions(
        segments=[{"speaker": "A", "text": "x"}],
        base_name="sample",
        transcript_dir=str(tmp_path),
    )
    assert result["total_interactions_count"] == 1
    assert "timeline" in calls
    assert "network" in calls
    assert calls.count("speaker_timeline") == 2


def test_interactions_analysis_module_save_results_includes_timelines(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Regression: AnalysisModule path must persist timeline charts too."""
    from unittest.mock import MagicMock

    from transcriptx.core.analysis.interactions.analysis import InteractionsAnalysis

    calls: list[str] = []

    def _mark(name: str):
        def _fn(*_args, **_kwargs):
            calls.append(name)

        return _fn

    monkeypatch.setattr(
        "transcriptx.core.analysis.interactions.analysis.create_combined_timeline",
        _mark("timeline"),
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.interactions.analysis.create_interaction_network",
        _mark("network"),
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.interactions.analysis.create_interaction_network_graph",
        _mark("network_graph"),
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.interactions.analysis.create_interaction_heatmap",
        _mark("heatmap"),
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.interactions.analysis.create_dominance_analysis",
        _mark("dominance"),
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.interactions.analysis.create_speaker_timeline_charts",
        _mark("speaker_timeline"),
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.interactions.analysis.create_analysis_summary",
        lambda *_a, **_k: None,
    )

    output_service = MagicMock()
    output_service.base_name = "sample"
    structure = MagicMock()
    structure.global_charts_dir = tmp_path / "charts" / "global"
    structure.global_charts_dir.mkdir(parents=True)
    output_service.get_output_structure.return_value = structure

    results = {
        "interactions": [
            {
                "timestamp": 1.0,
                "speaker_a": "Alice",
                "speaker_b": "Bob",
                "interaction_type": "response",
                "speaker_a_text": "hello",
                "speaker_b_text": "hi",
                "gap_before": 0.2,
                "overlap": 0.0,
                "speaker_a_start": 0.0,
                "speaker_a_end": 1.0,
                "speaker_b_start": 1.2,
                "speaker_b_end": 2.0,
            }
        ],
        "total_interactions_count": 1,
        "unique_speakers": 2,
    }
    InteractionsAnalysis()._save_results(results, output_service)

    assert "timeline" in calls
    assert "speaker_timeline" in calls
    assert "heatmap" in calls
    assert "dominance" in calls
    assert "network" in calls
