"""Offline unit tests for interactions visualization chart specs."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from transcriptx.core.analysis.interactions.events import InteractionEvent
from transcriptx.core.analysis.interactions.visualization import (
    create_combined_timeline,
    create_dominance_analysis,
    create_interaction_heatmap,
    create_interaction_network,
    create_speaker_timeline_charts,
)
from transcriptx.core.viz.specs import (
    BarCategoricalSpec,
    HeatmapMatrixSpec,
    LineTimeSeriesSpec,
)


def _event(
    *,
    timestamp: float = 60.0,
    speaker_a: str = "Alice",
    speaker_b: str = "Bob",
    interaction_type: str = "response",
) -> InteractionEvent:
    return InteractionEvent(
        timestamp=timestamp,
        speaker_a=speaker_a,
        speaker_b=speaker_b,
        interaction_type=interaction_type,
        speaker_a_text="hello",
        speaker_b_text="hi",
        gap_before=0.2,
        overlap=0.0,
        speaker_a_start=timestamp - 1.0,
        speaker_a_end=timestamp,
        speaker_b_start=timestamp,
        speaker_b_end=timestamp + 1.0,
    )


def _matrix_results(
    *,
    interruptions: int = 1,
    responses: int = 2,
) -> dict[str, Any]:
    return {
        "interaction_matrix": {
            "Alice": {
                "Bob": {"interruptions": interruptions, "responses": responses},
            },
            "Bob": {
                "Alice": {"interruptions": 0, "responses": 1},
            },
        },
        "dominance_scores": {"Alice": 0.8, "Bob": 0.4},
    }


@pytest.mark.unit
def test_create_combined_timeline_saves_line_spec() -> None:
    output_service = MagicMock()
    interactions = [
        _event(timestamp=30.0, interaction_type="response"),
        _event(timestamp=90.0, interaction_type="interruption_overlap"),
        _event(timestamp=120.0, interaction_type="interruption_gap"),
    ]

    create_combined_timeline(
        interactions, output_service=output_service, base_name="sample"
    )

    output_service.save_chart.assert_called_once()
    spec, kwargs = output_service.save_chart.call_args
    chart_spec = spec[0]
    assert kwargs["chart_type"] == "timeline"
    assert isinstance(chart_spec, LineTimeSeriesSpec)
    assert chart_spec.viz_id == "interactions.timeline.global"
    assert chart_spec.module == "interactions"
    assert chart_spec.markers is True
    assert len(chart_spec.series) == 3
    assert {s["name"] for s in chart_spec.series} == {
        "Interruption Overlap",
        "Interruption Gap",
        "Response",
    }


@pytest.mark.unit
def test_create_combined_timeline_early_returns() -> None:
    output_service = MagicMock()
    create_combined_timeline([], output_service=output_service, base_name="sample")
    create_combined_timeline([_event()], output_service=None, base_name="sample")
    output_service.save_chart.assert_not_called()


@pytest.mark.unit
def test_create_combined_timeline_warns_on_speaker_map() -> None:
    output_service = MagicMock()
    with pytest.warns(DeprecationWarning, match="speaker_map"):
        create_combined_timeline(
            [_event()],
            speaker_map={"A": "Alice"},
            output_service=output_service,
            base_name="sample",
        )
    assert output_service.save_chart.called


@pytest.mark.unit
def test_create_interaction_network_saves_heatmap() -> None:
    output_service = MagicMock()
    create_interaction_network(_matrix_results(), output_service, "sample")

    output_service.save_chart.assert_called_once()
    spec = output_service.save_chart.call_args.args[0]
    assert output_service.save_chart.call_args.kwargs["chart_type"] == "network"
    assert isinstance(spec, HeatmapMatrixSpec)
    assert spec.viz_id == "interactions.network.global"
    assert spec.x_labels == ["Alice", "Bob"]
    assert spec.y_labels == ["Alice", "Bob"]
    # Alice->Bob: 1 interruption + 2 responses = 3
    assert spec.z[0][1] == 3
    # Bob->Alice: 0 + 1 = 1
    assert spec.z[1][0] == 1


@pytest.mark.unit
def test_create_interaction_network_skips_empty_matrix() -> None:
    output_service = MagicMock()
    create_interaction_network({"interaction_matrix": {}}, output_service, "sample")
    output_service.save_chart.assert_not_called()


@pytest.mark.unit
def test_create_interaction_heatmap_saves_both_matrices() -> None:
    output_service = MagicMock()
    create_interaction_heatmap(_matrix_results(), output_service, "sample")

    assert output_service.save_chart.call_count == 2
    specs = [c.args[0] for c in output_service.save_chart.call_args_list]
    assert all(isinstance(s, HeatmapMatrixSpec) for s in specs)
    assert {s.viz_id for s in specs} == {
        "interactions.heatmap_interruptions.global",
        "interactions.heatmap_responses.global",
    }
    interrupt_spec = next(s for s in specs if s.name == "heatmap_interruptions")
    response_spec = next(s for s in specs if s.name == "heatmap_responses")
    assert interrupt_spec.notes is None
    assert response_spec.notes is None
    assert interrupt_spec.z[0][1] == 1
    assert response_spec.z[0][1] == 2


@pytest.mark.unit
def test_create_interaction_heatmap_notes_when_totals_zero() -> None:
    output_service = MagicMock()
    create_interaction_heatmap(
        {
            "interaction_matrix": {
                "Alice": {"Bob": {"interruptions": 0, "responses": 0}},
                "Bob": {"Alice": {"interruptions": 0, "responses": 0}},
            }
        },
        output_service,
        "sample",
    )
    specs = [c.args[0] for c in output_service.save_chart.call_args_list]
    assert all(s.notes == "None detected in this transcript." for s in specs)


@pytest.mark.unit
def test_create_dominance_analysis_saves_bar_spec() -> None:
    output_service = MagicMock()
    create_dominance_analysis(_matrix_results(), output_service, "sample")

    output_service.save_chart.assert_called_once()
    spec = output_service.save_chart.call_args.args[0]
    assert output_service.save_chart.call_args.kwargs["chart_type"] == "dominance"
    assert isinstance(spec, BarCategoricalSpec)
    assert spec.viz_id == "interactions.dominance.global"
    assert list(spec.categories) == ["Alice", "Bob"]
    assert list(spec.values) == [0.8, 0.4]


@pytest.mark.unit
def test_create_dominance_analysis_skips_empty_scores() -> None:
    output_service = MagicMock()
    create_dominance_analysis({"dominance_scores": {}}, output_service, "sample")
    output_service.save_chart.assert_not_called()


@pytest.mark.unit
def test_create_speaker_timeline_charts_saves_per_speaker() -> None:
    output_service = MagicMock()
    interactions = [
        _event(timestamp=30.0, interaction_type="response"),
        _event(
            timestamp=90.0,
            speaker_a="Bob",
            speaker_b="Alice",
            interaction_type="interruption_overlap",
        ),
    ]

    create_speaker_timeline_charts(
        interactions, output_service=output_service, base_name="sample"
    )

    assert output_service.save_chart.call_count == 2
    specs = [c.args[0] for c in output_service.save_chart.call_args_list]
    assert all(isinstance(s, LineTimeSeriesSpec) for s in specs)
    assert {s.viz_id for s in specs} == {"interactions.timeline.speaker"}
    assert {s.speaker for s in specs} == {"Alice", "Bob"}
    assert all(s.scope == "speaker" for s in specs)


@pytest.mark.unit
def test_create_speaker_timeline_charts_skips_unnamed_and_missing_service() -> None:
    output_service = MagicMock()
    create_speaker_timeline_charts(
        [
            _event(speaker_a="SPEAKER_00", speaker_b="Bob"),
            _event(speaker_a="", speaker_b="Alice"),
        ],
        output_service=output_service,
        base_name="sample",
    )
    output_service.save_chart.assert_not_called()

    create_speaker_timeline_charts([_event()], output_service=None, base_name="sample")


@pytest.mark.unit
def test_create_speaker_timeline_charts_warns_on_speaker_map() -> None:
    output_service = MagicMock()
    with pytest.warns(DeprecationWarning, match="speaker_map"):
        create_speaker_timeline_charts(
            [_event()],
            speaker_map={"A": "Alice"},
            output_service=output_service,
            base_name="sample",
        )
    assert output_service.save_chart.call_count == 2
