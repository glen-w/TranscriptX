"""No-signal policy tests for contract-driven mpl renderer."""

from __future__ import annotations

import pytest
from transcriptx.core.utils.lazy_imports import get_matplotlib_pyplot

from transcriptx.core.viz.mpl.contracts import NO_SIGNAL_MESSAGE
from transcriptx.core.viz.mpl.renderers.bar_categorical import bar_has_signal
from transcriptx.core.viz.specs import (
    BarCategoricalSpec,
    BoxSpec,
    HeatmapMatrixSpec,
    LineTimeSeriesSpec,
    NetworkGraphSpec,
    ScatterSeries,
    ScatterSpec,
)
from transcriptx.core.viz.mpl_renderer import render_mpl


def _overlay_messages(fig) -> list[str]:
    return [t.get_text() for ax in fig.axes for t in ax.texts]


def _jitter_offsets(fig) -> list[tuple[float, float]]:
    offsets: list[tuple[float, float]] = []
    for ax in fig.axes:
        for collection in ax.collections:
            for off in collection.get_offsets():
                offsets.append((float(off[0]), float(off[1])))
    return offsets


@pytest.mark.parametrize(
    ("builder", "expected_message"),
    [
        (
            lambda: LineTimeSeriesSpec(
                viz_id="line.missing",
                module="tests",
                name="line_missing",
                scope="global",
                chart_intent="line_timeseries",
                title="x",
                series=[],
            ),
            "series is required for line_timeseries charts",
        ),
        (
            lambda: HeatmapMatrixSpec(
                viz_id="heat.missing",
                module="tests",
                name="heat_missing",
                scope="global",
                chart_intent="heatmap_matrix",
                title="x",
                z=[],
            ),
            "z is required for heatmap_matrix charts",
        ),
        (
            lambda: BoxSpec(
                viz_id="box.missing",
                module="tests",
                name="box_missing",
                scope="global",
                chart_intent="box_plot",
                title="x",
                series=[],
            ),
            "series is required for box_plot charts",
        ),
        (
            lambda: NetworkGraphSpec(
                viz_id="net.missing.nodes",
                module="tests",
                name="net_missing_nodes",
                scope="global",
                chart_intent="network_graph",
                title="x",
                nodes=[],
                edges=[{"source": "A", "target": "B", "weight": 1}],
            ),
            "nodes are required for network_graph charts",
        ),
        (
            lambda: NetworkGraphSpec(
                viz_id="net.missing.edges",
                module="tests",
                name="net_missing_edges",
                scope="global",
                chart_intent="network_graph",
                title="x",
                nodes=[{"id": "A", "label": "A"}],
                edges=[],
            ),
            "edges are required for network_graph charts",
        ),
        (
            lambda: ScatterSpec(
                viz_id="scat.missing",
                module="tests",
                name="scat_missing",
                scope="global",
                chart_intent="scatter",
                title="x",
            ),
            "series or x/y is required for scatter charts",
        ),
    ],
)
def test_absent_required_payload_raises(builder, expected_message: str) -> None:
    with pytest.raises(ValueError, match=expected_message):
        render_mpl(builder())


def test_all_zero_line_payload_overlays() -> None:
    spec = LineTimeSeriesSpec(
        viz_id="line.zero",
        module="tests",
        name="line_zero",
        scope="global",
        chart_intent="line_timeseries",
        title="Line zero",
        series=[{"name": "s", "x": [0, 1, 2], "y": [0, 0, 0]}],
    )
    fig = render_mpl(spec)
    assert NO_SIGNAL_MESSAGE in _overlay_messages(fig)


def test_constant_non_zero_heatmap_no_overlay() -> None:
    spec = HeatmapMatrixSpec(
        viz_id="heat.constant.nonzero",
        module="tests",
        name="heat_constant_nonzero",
        scope="global",
        chart_intent="heatmap_matrix",
        title="Heat const",
        z=[[5, 5], [5, 5]],
        x_labels=["A", "B"],
        y_labels=["A", "B"],
    )
    fig = render_mpl(spec)
    assert NO_SIGNAL_MESSAGE not in _overlay_messages(fig)


def test_present_but_non_numeric_scatter_overlays() -> None:
    spec = ScatterSpec(
        viz_id="scatter.nonnumeric",
        module="tests",
        name="scatter_nonnumeric",
        scope="global",
        chart_intent="scatter",
        title="Scatter",
        series=[ScatterSeries(name="s", x=[0, 1], y=["a", "b"])],
    )
    fig = render_mpl(spec)
    assert NO_SIGNAL_MESSAGE in _overlay_messages(fig)


def test_mixed_numeric_and_non_numeric_scatter_uses_numeric_signal() -> None:
    spec = ScatterSpec(
        viz_id="scatter.mixed",
        module="tests",
        name="scatter_mixed",
        scope="global",
        chart_intent="scatter",
        title="Scatter",
        series=[ScatterSeries(name="s", x=[0, 1, 2], y=["bad", "0", "2.0"])],
    )
    fig = render_mpl(spec)
    assert NO_SIGNAL_MESSAGE not in _overlay_messages(fig)


def test_numeric_string_scatter_does_not_overlay() -> None:
    spec = ScatterSpec(
        viz_id="scatter.numeric.strings",
        module="tests",
        name="scatter_numeric_strings",
        scope="global",
        chart_intent="scatter",
        title="Scatter",
        series=[ScatterSeries(name="s", x=[0, 1], y=["1.5", "2.0"])],
    )
    fig = render_mpl(spec)
    assert NO_SIGNAL_MESSAGE not in _overlay_messages(fig)


def test_bar_flat_categories_present_values_empty_overlays() -> None:
    spec = BarCategoricalSpec(
        viz_id="bar.flat.empty",
        module="tests",
        name="bar_flat_empty",
        scope="global",
        chart_intent="bar_categorical",
        title="Bar",
        categories=["A", "B"],
        values=[0, 0],
        series=None,
    )
    assert bar_has_signal(spec) is False
    fig = render_mpl(spec)
    assert NO_SIGNAL_MESSAGE in _overlay_messages(fig)


def test_bar_grouped_non_numeric_values_overlays() -> None:
    spec = BarCategoricalSpec(
        viz_id="bar.grouped.nonnumeric",
        module="tests",
        name="bar_grouped_nonnumeric",
        scope="global",
        chart_intent="bar_categorical",
        title="Bar",
        series=[{"name": "s", "categories": ["A", "B"], "values": ["x", "y"]}],
    )
    assert bar_has_signal(spec) is False
    fig = render_mpl(spec)
    assert NO_SIGNAL_MESSAGE in _overlay_messages(fig)


def test_bar_grouped_numeric_string_values_do_not_overlay() -> None:
    spec = BarCategoricalSpec(
        viz_id="bar.grouped.numeric_strings",
        module="tests",
        name="bar_grouped_numeric_strings",
        scope="global",
        chart_intent="bar_categorical",
        title="Bar",
        series=[{"name": "s", "categories": ["A", "B"], "values": ["1", "2.5"]}],
    )
    assert bar_has_signal(spec) is True
    fig = render_mpl(spec)
    assert NO_SIGNAL_MESSAGE not in _overlay_messages(fig)


def test_bar_grouped_empty_series_overlays() -> None:
    spec = BarCategoricalSpec(
        viz_id="bar.grouped.empty",
        module="tests",
        name="bar_grouped_empty",
        scope="global",
        chart_intent="bar_categorical",
        title="Bar",
        categories=["A", "B"],
        values=[1, 2],
        series=[],
    )
    assert bar_has_signal(spec) is False
    fig = render_mpl(spec)
    assert NO_SIGNAL_MESSAGE in _overlay_messages(fig)


def test_bar_grouped_all_zero_values_overlays() -> None:
    spec = BarCategoricalSpec(
        viz_id="bar.grouped.zero",
        module="tests",
        name="bar_grouped_zero",
        scope="global",
        chart_intent="bar_categorical",
        title="Bar",
        series=[
            {"name": "s1", "categories": ["A", "B"], "values": [0, 0]},
            {"name": "s2", "categories": ["A", "B"], "values": [0, 0]},
        ],
    )
    fig = render_mpl(spec)
    assert NO_SIGNAL_MESSAGE in _overlay_messages(fig)


def test_network_all_zero_edges_overlays() -> None:
    spec = NetworkGraphSpec(
        viz_id="net.zero",
        module="tests",
        name="net_zero",
        scope="global",
        chart_intent="network_graph",
        title="Network",
        nodes=[{"id": "A", "label": "A"}, {"id": "B", "label": "B"}],
        edges=[{"source": "A", "target": "B", "weight": 0}],
    )
    fig = render_mpl(spec)
    assert NO_SIGNAL_MESSAGE in _overlay_messages(fig)


def test_network_positive_weight_does_not_overlay() -> None:
    spec = NetworkGraphSpec(
        viz_id="net.positive",
        module="tests",
        name="net_positive",
        scope="global",
        chart_intent="network_graph",
        title="Network",
        nodes=[{"id": "A", "label": "A"}, {"id": "B", "label": "B"}],
        edges=[{"source": "A", "target": "B", "weight": 3}],
    )
    fig = render_mpl(spec)
    assert NO_SIGNAL_MESSAGE not in _overlay_messages(fig)


def test_heatmap_zero_payload_with_notes_still_uses_standard_overlay_only() -> None:
    spec = HeatmapMatrixSpec(
        viz_id="heat.zero.notes",
        module="tests",
        name="heat_zero_notes",
        scope="global",
        chart_intent="heatmap_matrix",
        title="Heat",
        notes="custom note should not render",
        z=[[0, 0], [0, 0]],
        x_labels=["A", "B"],
        y_labels=["A", "B"],
    )
    fig = render_mpl(spec)
    messages = _overlay_messages(fig)
    assert NO_SIGNAL_MESSAGE in messages
    assert "custom note should not render" not in messages


def test_box_all_empty_y_overlays() -> None:
    spec = BoxSpec(
        viz_id="box.empty.y",
        module="tests",
        name="box_empty_y",
        scope="global",
        chart_intent="box_plot",
        title="Box",
        series=[{"name": "s1", "y": []}, {"name": "s2", "y": []}],
    )
    fig = render_mpl(spec)
    assert NO_SIGNAL_MESSAGE in _overlay_messages(fig)


def test_box_multi_series_without_x_renders_one_box_per_series() -> None:
    spec = BoxSpec(
        viz_id="box.no.x.multiple",
        module="tests",
        name="box_no_x_multiple",
        scope="global",
        chart_intent="box_plot",
        title="Box",
        series=[
            {"name": "s1", "y": [1.0, 2.0]},
            {"name": "s2", "y": [3.0, 4.0]},
        ],
    )
    fig = render_mpl(spec)
    ax = fig.axes[0]
    assert [t.get_text() for t in ax.get_xticklabels()] == ["s1", "s2"]


def test_box_multi_series_without_x_uses_default_series_labels_when_missing_names() -> (
    None
):
    spec = BoxSpec(
        viz_id="box.no.x.default.labels",
        module="tests",
        name="box_no_x_default_labels",
        scope="global",
        chart_intent="box_plot",
        title="Box",
        series=[{"y": [1.0, 2.0]}, {"y": [3.0, 4.0]}],
    )
    fig = render_mpl(spec)
    ax = fig.axes[0]
    assert [t.get_text() for t in ax.get_xticklabels()] == ["series_0", "series_1"]


def test_deterministic_jitter_same_identity_matches() -> None:
    spec = BoxSpec(
        viz_id="box.jitter.same",
        module="tests",
        name="box_jitter_same",
        scope="global",
        chart_intent="box_plot",
        title="Box",
        show_points=True,
        series=[{"name": "s1", "y": [1.0, 2.0, 3.0]}],
    )
    fig1 = render_mpl(spec)
    fig2 = render_mpl(spec)
    assert _jitter_offsets(fig1) == _jitter_offsets(fig2)


def test_deterministic_jitter_different_identity_differs() -> None:
    spec_a = BoxSpec(
        viz_id="box.jitter.a",
        module="tests",
        name="box_jitter",
        scope="global",
        chart_intent="box_plot",
        title="Box",
        show_points=True,
        series=[{"name": "s1", "y": [1.0, 2.0, 3.0]}],
    )
    spec_b = BoxSpec(
        viz_id="box.jitter.b",
        module="tests",
        name="box_jitter",
        scope="global",
        chart_intent="box_plot",
        title="Box",
        show_points=True,
        series=[{"name": "s1", "y": [1.0, 2.0, 3.0]}],
    )
    fig_a = render_mpl(spec_a)
    fig_b = render_mpl(spec_b)
    assert _jitter_offsets(fig_a) != _jitter_offsets(fig_b)


def test_bar_mode_split_symmetry_flat_grouped_populated_grouped_empty() -> None:
    flat = BarCategoricalSpec(
        viz_id="bar.mode.flat",
        module="tests",
        name="bar_mode_flat",
        scope="global",
        chart_intent="bar_categorical",
        title="Bar",
        categories=["A"],
        values=[1],
        series=None,
    )
    grouped_populated = BarCategoricalSpec(
        viz_id="bar.mode.grouped_populated",
        module="tests",
        name="bar_mode_grouped_populated",
        scope="global",
        chart_intent="bar_categorical",
        title="Bar",
        series=[{"name": "s", "categories": ["A"], "values": [1]}],
    )
    grouped_empty = BarCategoricalSpec(
        viz_id="bar.mode.grouped_empty",
        module="tests",
        name="bar_mode_grouped_empty",
        scope="global",
        chart_intent="bar_categorical",
        title="Bar",
        series=[],
    )

    assert bar_has_signal(flat) is True
    assert bar_has_signal(grouped_populated) is True
    assert bar_has_signal(grouped_empty) is False

    flat_fig = render_mpl(flat)
    grouped_populated_fig = render_mpl(grouped_populated)
    grouped_empty_fig = render_mpl(grouped_empty)
    assert NO_SIGNAL_MESSAGE not in _overlay_messages(flat_fig)
    assert NO_SIGNAL_MESSAGE not in _overlay_messages(grouped_populated_fig)
    assert NO_SIGNAL_MESSAGE in _overlay_messages(grouped_empty_fig)


@pytest.fixture(autouse=True)
def _close_figures_after_test():
    yield
    get_matplotlib_pyplot().close("all")
