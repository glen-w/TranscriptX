"""Offline unit tests for transcriptx.core.viz.charts helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.viz import charts as ch
from transcriptx.core.viz.specs import (
    BarCategoricalSpec,
    BoxSpec,
    HeatmapMatrixSpec,
    LineTimeSeriesSpec,
    NetworkGraphSpec,
    PreRenderedFigureSpec,
    ScatterSeries,
    ScatterSpec,
)


def _base(**kw):
    defaults = dict(
        viz_id="viz.test",
        module="test",
        name="n",
        scope="global",
        chart_intent="line_timeseries",
        title="t",
    )
    defaults.update(kw)
    return defaults


@pytest.fixture(autouse=True)
def _reset_plotly_flags():
    ch._plotly_available = None
    ch._warned_missing_plotly = False
    yield
    ch._plotly_available = None
    ch._warned_missing_plotly = False


@pytest.mark.unit
def test_is_plotly_available_true_and_false() -> None:
    with patch.object(ch, "optional_import", return_value=MagicMock()):
        assert ch.is_plotly_available() is True
        assert ch.is_plotly_available() is True
    ch._plotly_available = None
    with patch.object(ch, "optional_import", side_effect=ImportError("x")):
        assert ch.is_plotly_available() is False


@pytest.mark.unit
def test_warn_missing_plotly_once_module_and_state() -> None:
    with patch.object(ch.logger, "warning") as warn:
        ch.warn_missing_plotly_once()
        ch.warn_missing_plotly_once()
    assert warn.call_count == 1
    state: dict[str, bool] = {}
    with patch.object(ch.logger, "warning") as warn2:
        ch.warn_missing_plotly_once(state)
        ch.warn_missing_plotly_once(state)
    assert warn2.call_count == 1
    assert state["warned_plotly_missing"] is True


@pytest.mark.unit
def test_require_plotly_raises_when_missing() -> None:
    with patch.object(ch, "is_plotly_available", return_value=False):
        with pytest.raises(RuntimeError, match="Plotly is required"):
            ch.require_plotly()


@pytest.mark.unit
def test_save_static_chart_ok_and_bad_suffix(tmp_path: Path) -> None:
    fig = MagicMock()
    path = tmp_path / "c.png"
    assert ch.save_static_chart(fig, path, dpi=100) == path
    fig.savefig.assert_called_once()
    with pytest.raises(ValueError, match="must end with .png"):
        ch.save_static_chart(fig, tmp_path / "c.jpg")


@pytest.mark.unit
def test_save_dynamic_chart_branches(tmp_path: Path) -> None:
    assert ch.save_dynamic_chart(None, tmp_path / "a.html") is None
    with pytest.raises(ValueError, match="must end with .html"):
        ch.save_dynamic_chart(MagicMock(), tmp_path / "a.png")

    with (
        patch.object(ch, "is_plotly_available", return_value=False),
        patch.object(ch, "_warn_missing_plotly_once") as warn,
    ):
        assert ch.save_dynamic_chart(MagicMock(), tmp_path / "a.html") is None
        warn.assert_called_once()

    pytest.importorskip("plotly", reason="plotly extra not installed")
    with (
        patch.object(ch, "is_plotly_available", return_value=True),
        patch("plotly.io.write_html") as write_html,
    ):
        out = ch.save_dynamic_chart(MagicMock(), tmp_path / "b.html")
    assert out == tmp_path / "b.html"
    write_html.assert_called_once()


@pytest.mark.unit
def test_render_plotly_returns_none_without_plotly() -> None:
    spec = LineTimeSeriesSpec(
        **_base(chart_intent="line_timeseries"),
        series=[{"x": [1], "y": [2]}],
    )
    with patch.object(ch, "is_plotly_available", return_value=False):
        assert ch.render_plotly(spec) is None


@pytest.mark.unit
def test_render_plotly_all_intents() -> None:
    fake_go = MagicMock()
    fig = MagicMock()
    fake_go.Figure.return_value = fig
    fake_go.Scatter = MagicMock(return_value=MagicMock())
    fake_go.Heatmap = MagicMock(return_value=MagicMock())
    fake_go.Bar = MagicMock(return_value=MagicMock())
    fake_go.Box = MagicMock(return_value=MagicMock())

    import sys

    plotly_mod = MagicMock()
    plotly_mod.graph_objects = fake_go
    previous_plotly = sys.modules.get("plotly")
    previous_go = sys.modules.get("plotly.graph_objects")
    sys.modules["plotly"] = plotly_mod
    sys.modules["plotly.graph_objects"] = fake_go
    try:
        with patch.object(ch, "is_plotly_available", return_value=True):
            line = LineTimeSeriesSpec(
                **_base(chart_intent="line_timeseries"),
                series=[{"x": [1, 2], "y": [3, 4], "name": "a", "text": ["t1", "t2"]}],
                markers=True,
                x_label="x",
                y_label="y",
            )
            assert ch.render_plotly(line) is fig

            scatter = ScatterSpec(
                **_base(chart_intent="scatter"),
                series=[
                    ScatterSeries(
                        name="s",
                        x=[1, 2],
                        y=["a", "b"],
                        text=["t1", "t2"],
                        marker={"size": 5},
                    )
                ],
                mode="markers",
                y_is_categorical=None,
            )
            assert ch.render_plotly(scatter) is fig
            fig.update_yaxes.assert_called()

            heat = HeatmapMatrixSpec(
                **_base(chart_intent="heatmap_matrix"),
                z=[[1, 2], [3, 4]],
                x_labels=["a", "b"],
                y_labels=["c", "d"],
                zmin=0,
                zmax=4,
            )
            assert ch.render_plotly(heat) is fig

            bar = BarCategoricalSpec(
                **_base(chart_intent="bar_categorical"),
                categories=["a", "b"],
                values=[1.0, 2.0],
                orientation="vertical",
            )
            assert ch.render_plotly(bar) is fig

            bar_h = BarCategoricalSpec(
                **_base(chart_intent="bar_categorical"),
                categories=["a"],
                values=[1.0],
                orientation="horizontal",
                series=[{"name": "n", "categories": ["a"], "values": [3.0]}],
            )
            assert ch.render_plotly(bar_h) is fig

            box = BoxSpec(
                **_base(chart_intent="box_plot"),
                series=[{"x": ["g"], "y": [1, 2, 3], "name": "b"}],
                show_points=True,
            )
            assert ch.render_plotly(box) is fig

            net = NetworkGraphSpec(
                **_base(chart_intent="network_graph"),
                nodes=[
                    {"id": "a", "label": "A", "size": 30, "color": "red"},
                    {"id": "b", "label": "B"},
                ],
                edges=[{"source": "a", "target": "b", "weight": 2, "label": "e"}],
                node_positions={"a": (0.0, 0.0), "b": (1.0, 1.0)},
            )
            assert ch.render_plotly(net) is fig

            net2 = NetworkGraphSpec(
                **_base(chart_intent="network_graph"),
                nodes=[{"id": "a", "label": "A"}],
                edges=[{"source": "a", "target": "a"}],
            )
            with patch("networkx.spring_layout", return_value={"a": (0.1, 0.2)}):
                assert ch.render_plotly(net2) is fig

            pre = PreRenderedFigureSpec(
                **_base(chart_intent="pre_rendered"),
                figure=object(),
                labels=["a"],
                values=[1.0],
            )
            assert ch.render_plotly(pre) is None
    finally:
        if previous_plotly is None:
            sys.modules.pop("plotly", None)
        else:
            sys.modules["plotly"] = previous_plotly
        if previous_go is None:
            sys.modules.pop("plotly.graph_objects", None)
        else:
            sys.modules["plotly.graph_objects"] = previous_go
