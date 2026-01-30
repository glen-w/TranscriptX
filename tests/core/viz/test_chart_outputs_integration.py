"""Integration tests: verify chart outputs for acts, conversation_loops, echoes (where implemented)."""

import tempfile
from pathlib import Path

import pytest

from transcriptx.core.viz.mpl_renderer import render_mpl
from transcriptx.core.viz.specs import (
    BarCategoricalSpec,
    HeatmapMatrixSpec,
    LineTimeSeriesSpec,
    NetworkGraphSpec,
    ScatterSpec,
    ScatterSeries,
)
from transcriptx.core.output.output_service import create_output_service


def test_acts_chart_specs_render() -> None:
    """Acts: bar_categorical and line_timeseries specs render without error."""
    # Per-speaker bar (acts_bar)
    spec_bar = BarCategoricalSpec(
        viz_id="acts.acts_bar.speaker",
        module="acts",
        name="acts_bar",
        scope="speaker",
        speaker="Alice",
        chart_intent="bar_categorical",
        title="Dialogue Acts – Alice",
        x_label="Act Type",
        y_label="Count",
        categories=["statement", "question", "backchannel"],
        values=[10, 3, 2],
    )
    fig = render_mpl(spec_bar)
    assert fig is not None

    # Temporal (acts over time)
    spec_temporal = LineTimeSeriesSpec(
        viz_id="acts.acts_temporal.speaker",
        module="acts",
        name="acts_temporal",
        scope="speaker",
        speaker="Alice",
        chart_intent="line_timeseries",
        title="Dialogue Acts Over Time – Alice",
        x_label="Time (minutes)",
        y_label="Dialogue Act (index)",
        markers=True,
        series=[{"name": "Alice", "x": [0.0, 1.0, 2.0], "y": [0, 1, 0]}],
    )
    fig = render_mpl(spec_temporal)
    assert fig is not None


def test_conversation_loops_chart_specs_render() -> None:
    """Conversation loops: network_graph, scatter_events (timeline), bar_categorical render."""
    # Loop network
    spec_network = NetworkGraphSpec(
        viz_id="conversation_loops.loop_network.global",
        module="conversation_loops",
        name="loop_network",
        scope="global",
        chart_intent="network_graph",
        title="Conversation Loop Network - test",
        nodes=[
            {"id": "A", "label": "Alice", "size": 30, "color": "lightblue"},
            {"id": "B", "label": "Bob", "size": 30, "color": "lightblue"},
        ],
        edges=[{"source": "A", "target": "B", "weight": 2, "label": "2"}],
        node_positions={"A": (0.0, 0.0), "B": (1.0, 0.0)},
    )
    fig = render_mpl(spec_network)
    assert fig is not None

    # Loop timeline (scatter)
    spec_timeline = ScatterSpec(
        viz_id="conversation_loops.loop_timeline.global",
        module="conversation_loops",
        name="loop_timeline",
        scope="global",
        chart_intent="scatter_events",
        title="Conversation Loop Timeline - test",
        x_label="Time (minutes)",
        y_label="Loop ID",
        mode="markers",
        series=[
            ScatterSeries(
                name="Loop 1",
                x=[0.5, 1.0, 1.5],
                y=["Loop 1", "Loop 1", "Loop 1"],
                text=["Alice: question", "Bob: statement", "Alice: backchannel"],
            )
        ],
        y_is_categorical=True,
    )
    fig = render_mpl(spec_timeline)
    assert fig is not None

    # Act patterns bar
    spec_bar = BarCategoricalSpec(
        viz_id="conversation_loops.act_patterns.global",
        module="conversation_loops",
        name="act_patterns",
        scope="global",
        chart_intent="bar_categorical",
        title="Conversation Loop Act Patterns - test",
        x_label="Act Pattern",
        y_label="Count",
        categories=["question → statement → backchannel"],
        values=[2],
    )
    fig = render_mpl(spec_bar)
    assert fig is not None


def test_echoes_chart_specs_render() -> None:
    """Echoes: heatmap_matrix and line_timeseries (timeline) render."""
    # Echo heatmap
    spec_heatmap = HeatmapMatrixSpec(
        viz_id="echoes.echo_heatmap.global",
        module="echoes",
        name="echo_heatmap",
        scope="global",
        chart_intent="heatmap_matrix",
        title="Echo Network Heatmap",
        x_label="To Speaker",
        y_label="From Speaker",
        z=[[0, 1], [2, 0]],
        x_labels=["Alice", "Bob"],
        y_labels=["Alice", "Bob"],
    )
    fig = render_mpl(spec_heatmap)
    assert fig is not None

    # Echo timeline
    spec_timeline = LineTimeSeriesSpec(
        viz_id="echoes.echo_timeline.global",
        module="echoes",
        name="echo_timeline",
        scope="global",
        chart_intent="line_timeseries",
        title="Echo Timeline",
        x_label="Time (seconds)",
        y_label="Score",
        markers=True,
        series=[{"name": "Echo", "x": [10.0, 20.0, 30.0], "y": [0.8, 0.6, 0.9]}],
    )
    fig = render_mpl(spec_timeline)
    assert fig is not None


def test_acts_conversation_loops_echoes_save_chart_roundtrip() -> None:
    """Save chart via OutputService for acts, conversation_loops, echoes (one each)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        transcript_path = str(Path(tmpdir) / "dummy_transcript.json")
        Path(transcript_path).write_text("{}")

        # Acts: bar
        os_acts = create_output_service(transcript_path, "acts", output_dir=tmpdir)
        spec_acts = BarCategoricalSpec(
            viz_id="acts.acts_bar.speaker",
            module="acts",
            name="acts_bar",
            scope="speaker",
            speaker="Alice",
            chart_intent="bar_categorical",
            title="Dialogue Acts – Alice",
            x_label="Act Type",
            y_label="Count",
            categories=["statement", "question"],
            values=[5, 2],
        )
        result_acts = os_acts.save_chart(spec_acts, chart_type="bar")
        assert result_acts.get("static") and Path(result_acts["static"]).exists()

        # Conversation loops: bar (act_patterns)
        os_loops = create_output_service(
            transcript_path, "conversation_loops", output_dir=tmpdir
        )
        spec_loops = BarCategoricalSpec(
            viz_id="conversation_loops.act_patterns.global",
            module="conversation_loops",
            name="act_patterns",
            scope="global",
            chart_intent="bar_categorical",
            title="Loop Act Patterns",
            x_label="Pattern",
            y_label="Count",
            categories=["q → s → b"],
            values=[1],
        )
        result_loops = os_loops.save_chart(spec_loops, chart_type="bar")
        assert result_loops.get("static") and Path(result_loops["static"]).exists()

        # Echoes: heatmap
        os_echoes = create_output_service(transcript_path, "echoes", output_dir=tmpdir)
        spec_echoes = HeatmapMatrixSpec(
            viz_id="echoes.echo_heatmap.global",
            module="echoes",
            name="echo_heatmap",
            scope="global",
            chart_intent="heatmap_matrix",
            title="Echo Heatmap",
            x_label="To",
            y_label="From",
            z=[[0, 1], [1, 0]],
            x_labels=["A", "B"],
            y_labels=["A", "B"],
        )
        result_echoes = os_echoes.save_chart(spec_echoes, chart_type="heatmap")
        assert result_echoes.get("static") and Path(result_echoes["static"]).exists()
