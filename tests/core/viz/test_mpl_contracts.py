"""Contract tests for mpl renderer dispatch and invariants."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from transcriptx.core.utils.lazy_imports import get_matplotlib_pyplot
from transcriptx.core.viz.mpl.contracts import (
    RenderContractError,
    TYPE_TO_INTENTS,
    seeded_rng_for,
)
from transcriptx.core.viz.mpl.dispatch import (
    get_renderer_registry,
    register,
    render_mpl,
)
from transcriptx.core.viz.mpl.empty_signal import get_probe_registry, register_probe
from transcriptx.core.viz.mpl_renderer import render_mpl as render_mpl_legacy
from transcriptx.core.viz.specs import (
    BarCategoricalSpec,
    BoxSpec,
    ChartSpec,
    HeatmapMatrixSpec,
    LineTimeSeriesSpec,
    NetworkGraphSpec,
    ScatterSeries,
    ScatterSpec,
)


@pytest.fixture(autouse=True)
def _close_figures_after_test():
    yield
    get_matplotlib_pyplot().close("all")


def _line_spec(
    *, notes: str | None = None, chart_intent: str = "line_timeseries"
) -> LineTimeSeriesSpec:
    return LineTimeSeriesSpec(
        viz_id="line.test",
        module="tests",
        name="line",
        scope="global",
        chart_intent=chart_intent,  # type: ignore[arg-type]
        title="Line",
        notes=notes,
        series=[{"name": "s", "x": [0, 1], "y": [1, 2]}],
    )


def _scatter_spec(
    *, notes: str | None = None, chart_intent: str = "scatter"
) -> ScatterSpec:
    return ScatterSpec(
        viz_id="scatter.test",
        module="tests",
        name="scatter",
        scope="global",
        chart_intent=chart_intent,  # type: ignore[arg-type]
        title="Scatter",
        notes=notes,
        series=[ScatterSeries(name="s", x=[0, 1], y=[1, 2])],
    )


def _heatmap_spec(
    *, notes: str | None = None, chart_intent: str = "heatmap_matrix"
) -> HeatmapMatrixSpec:
    return HeatmapMatrixSpec(
        viz_id="heat.test",
        module="tests",
        name="heat",
        scope="global",
        chart_intent=chart_intent,  # type: ignore[arg-type]
        title="Heat",
        notes=notes,
        z=[[1, 2], [3, 4]],
        x_labels=["A", "B"],
        y_labels=["A", "B"],
    )


def _bar_spec(
    *, notes: str | None = None, chart_intent: str = "bar_categorical"
) -> BarCategoricalSpec:
    return BarCategoricalSpec(
        viz_id="bar.test",
        module="tests",
        name="bar",
        scope="global",
        chart_intent=chart_intent,  # type: ignore[arg-type]
        title="Bar",
        notes=notes,
        categories=["A", "B"],
        values=[1, 2],
    )


def _box_spec(*, notes: str | None = None, chart_intent: str = "box_plot") -> BoxSpec:
    return BoxSpec(
        viz_id="box.test",
        module="tests",
        name="box",
        scope="global",
        chart_intent=chart_intent,  # type: ignore[arg-type]
        title="Box",
        notes=notes,
        series=[{"name": "s", "x": ["A", "A"], "y": [1, 2]}],
    )


def _network_spec(
    *, notes: str | None = None, chart_intent: str = "network_graph"
) -> NetworkGraphSpec:
    return NetworkGraphSpec(
        viz_id="net.test",
        module="tests",
        name="net",
        scope="global",
        chart_intent=chart_intent,  # type: ignore[arg-type]
        title="Network",
        notes=notes,
        nodes=[{"id": "A", "label": "Alice"}, {"id": "B", "label": "Bob"}],
        edges=[{"source": "A", "target": "B", "weight": 2}],
    )


def test_bare_chart_spec_is_not_renderable() -> None:
    spec = ChartSpec(
        viz_id="base",
        module="tests",
        name="base",
        scope="global",
        chart_intent="scatter",
        title="Base",
    )
    with pytest.raises(RenderContractError):
        render_mpl(spec)


def test_legacy_shim_exports_same_render_callable() -> None:
    assert render_mpl_legacy is render_mpl


def test_subclass_of_registered_spec_is_not_renderable() -> None:
    class MyScatter(ScatterSpec):
        pass

    spec = MyScatter(
        viz_id="my.scatter",
        module="tests",
        name="my_scatter",
        scope="global",
        chart_intent="scatter",
        title="Subclass",
        series=[ScatterSeries(name="s", x=[0], y=[1])],
    )
    with pytest.raises(RenderContractError):
        render_mpl(spec)


@pytest.mark.parametrize(
    ("factory", "wrong_intent"),
    [
        (_line_spec, "scatter"),
        (_scatter_spec, "line_timeseries"),
        (_heatmap_spec, "box_plot"),
        (_bar_spec, "network_graph"),
        (_box_spec, "heatmap_matrix"),
        (_network_spec, "bar_categorical"),
    ],
)
def test_mismatched_type_and_intent_raises(factory, wrong_intent: str) -> None:
    with pytest.raises(RenderContractError):
        render_mpl(factory(chart_intent=wrong_intent))


def test_scatter_accepts_both_intents() -> None:
    assert render_mpl(_scatter_spec(chart_intent="scatter")) is not None
    assert render_mpl(_scatter_spec(chart_intent="scatter_events")) is not None


@pytest.mark.parametrize(
    "spec",
    [
        _line_spec(notes="meta-note"),
        _scatter_spec(notes="meta-note"),
        _heatmap_spec(notes="meta-note"),
        _bar_spec(notes="meta-note"),
        _box_spec(notes="meta-note"),
        _network_spec(notes="meta-note"),
    ],
)
def test_notes_are_not_drawn_on_axes(spec: ChartSpec) -> None:
    fig = render_mpl(spec)
    all_text = [text.get_text() for ax in fig.axes for text in ax.texts]
    assert "meta-note" not in all_text


def test_box_mixed_x_raises_structural_error() -> None:
    spec = BoxSpec(
        viz_id="box.mixed",
        module="tests",
        name="box_mixed",
        scope="global",
        chart_intent="box_plot",
        title="Box mixed x",
        series=[
            {"name": "one", "x": ["A", "A"], "y": [1, 2]},
            {"name": "two", "y": [3, 4]},
        ],
    )
    with pytest.raises(RenderContractError):
        render_mpl(spec)


def test_network_endpoint_not_in_nodes_raises() -> None:
    spec = NetworkGraphSpec(
        viz_id="net.bad.edge",
        module="tests",
        name="net_bad_edge",
        scope="global",
        chart_intent="network_graph",
        title="Bad net",
        nodes=[{"id": "A", "label": "Alice"}],
        edges=[{"source": "A", "target": "B", "weight": 1}],
    )
    with pytest.raises(RenderContractError):
        render_mpl(spec)


def test_network_identity_combined_rejection() -> None:
    spec = NetworkGraphSpec(
        viz_id="net.bad.identity",
        module="tests",
        name="net_bad_identity",
        scope="global",
        chart_intent="network_graph",
        title="Bad identity",
        nodes=[{"label": "Alice"}],
        edges=[{"source": "Alice", "target": "Alice", "weight": 1}],
    )
    with pytest.raises(RenderContractError):
        render_mpl(spec)


def test_registry_completeness() -> None:
    renderer_keys = set(get_renderer_registry().keys())
    probe_keys = set(get_probe_registry().keys())
    contract_keys = set(TYPE_TO_INTENTS.keys())
    assert renderer_keys == contract_keys
    assert probe_keys == contract_keys


def test_decorator_level_guardrails() -> None:
    def _dummy_renderer(spec, plt):
        return None

    def _dummy_probe(spec):
        return True

    with pytest.raises(RenderContractError):
        register(ChartSpec)  # type: ignore[arg-type]
    with pytest.raises(RenderContractError):
        register_probe(ChartSpec)  # type: ignore[arg-type]

    class NotRegistered(ChartSpec):
        pass

    with pytest.raises(RenderContractError):
        register(NotRegistered)(_dummy_renderer)
    with pytest.raises(RenderContractError):
        register_probe(NotRegistered)(_dummy_probe)

    with pytest.raises(RenderContractError):
        register(ScatterSpec)(_dummy_renderer)
    with pytest.raises(RenderContractError):
        register_probe(ScatterSpec)(_dummy_probe)


def test_gatekeeper_ordering_mismatch_fails_before_loader() -> None:
    spec = _scatter_spec(chart_intent="line_timeseries")
    with patch(
        "transcriptx.core.viz.mpl.dispatch.get_matplotlib_pyplot",
        side_effect=AssertionError("loader should not be called"),
    ):
        with pytest.raises(RenderContractError):
            render_mpl(spec)


def test_gatekeeper_ordering_base_spec_fails_before_loader() -> None:
    spec = ChartSpec(
        viz_id="base",
        module="tests",
        name="base",
        scope="global",
        chart_intent="scatter",
        title="Base",
    )
    with patch(
        "transcriptx.core.viz.mpl.dispatch.get_matplotlib_pyplot",
        side_effect=AssertionError("loader should not be called"),
    ):
        with pytest.raises(RenderContractError):
            render_mpl(spec)


def test_gatekeeper_not_over_eager_loader_called_before_renderer_invariant_error() -> (
    None
):
    spec = BoxSpec(
        viz_id="box.bad.invariant",
        module="tests",
        name="box_bad_invariant",
        scope="global",
        chart_intent="box_plot",
        title="Bad",
        series=[
            {"name": "one", "x": ["A", "A"], "y": [1, 2]},
            {"name": "two", "y": [3, 4]},
        ],
    )
    with patch("transcriptx.core.viz.mpl.dispatch.get_matplotlib_pyplot") as loader:
        from transcriptx.core.utils.lazy_imports import get_matplotlib_pyplot

        loader.side_effect = get_matplotlib_pyplot
        with pytest.raises(RenderContractError):
            render_mpl(spec)
        assert loader.call_count == 1


def test_renderer_modules_do_not_reference_chart_intent() -> None:
    renderers_dir = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "transcriptx"
        / "core"
        / "viz"
        / "mpl"
        / "renderers"
    )
    offenders: list[str] = []
    for file in renderers_dir.glob("*.py"):
        if file.name == "__init__.py":
            continue
        if "chart_intent" in file.read_text(encoding="utf-8"):
            offenders.append(file.name)
    assert offenders == []


def test_seeded_rng_fallback_without_viz_id_is_stable() -> None:
    spec = LineTimeSeriesSpec(
        viz_id="",
        module="tests",
        name="rng_fallback",
        scope="global",
        chart_intent="line_timeseries",
        title="RNG fallback",
        series=[{"name": "s", "x": [0, 1], "y": [1, 2]}],
    )
    rng_a = seeded_rng_for(spec)
    rng_b = seeded_rng_for(spec)
    assert rng_a.random(4).tolist() == rng_b.random(4).tolist()


def test_seeded_rng_fallback_changes_with_identity_fields() -> None:
    spec_a = LineTimeSeriesSpec(
        viz_id="",
        module="tests",
        name="rng_fallback_a",
        scope="global",
        chart_intent="line_timeseries",
        title="RNG fallback",
        series=[{"name": "s", "x": [0, 1], "y": [1, 2]}],
    )
    spec_b = LineTimeSeriesSpec(
        viz_id="",
        module="tests",
        name="rng_fallback_b",
        scope="global",
        chart_intent="line_timeseries",
        title="RNG fallback",
        series=[{"name": "s", "x": [0, 1], "y": [1, 2]}],
    )
    assert (
        seeded_rng_for(spec_a).random(4).tolist()
        != seeded_rng_for(spec_b).random(4).tolist()
    )
