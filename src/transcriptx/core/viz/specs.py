"""Chart specification models for rendering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Sequence


@dataclass
class ChartSpec:
    """Base chart spec shared by all intents."""

    viz_id: str
    module: str
    name: str
    scope: Literal["global", "speaker"]
    chart_intent: Literal[
        "line_timeseries",
        "heatmap_matrix",
        "bar_categorical",
        "box_plot",
        "network_graph",
        "scatter",
        "scatter_events",
    ]
    title: str
    speaker: str | None = None
    x_label: str | None = None
    y_label: str | None = None
    notes: str | None = None

    def validate(self) -> None:
        if not self.viz_id:
            raise ValueError("viz_id is required")
        if not self.module:
            raise ValueError("module is required")
        if not self.name:
            raise ValueError("name is required")
        if self.scope == "speaker" and not self.speaker:
            raise ValueError("speaker is required for speaker-scope charts")


@dataclass
class LineTimeSeriesSpec(ChartSpec):
    """Spec for line time series charts."""

    series: Sequence[dict[str, Any]] = ()
    x_type: str | None = None
    y_type: str | None = None
    markers: bool = False

    def validate(self) -> None:
        super().validate()
        if not self.series:
            raise ValueError("series is required for line_timeseries charts")


@dataclass
class HeatmapMatrixSpec(ChartSpec):
    """Spec for heatmap matrix charts."""

    z: Sequence[Sequence[float]] = ()
    x_labels: Sequence[str] = ()
    y_labels: Sequence[str] = ()
    zmin: float | None = None
    zmax: float | None = None

    def validate(self) -> None:
        super().validate()
        if not self.z:
            raise ValueError("z is required for heatmap_matrix charts")


@dataclass
class BarCategoricalSpec(ChartSpec):
    """Spec for categorical bar charts."""

    categories: Sequence[str] = ()
    values: Sequence[float] = ()
    series: Sequence[dict[str, Any]] | None = None
    orientation: Literal["vertical", "horizontal"] = "vertical"

    def validate(self) -> None:
        super().validate()
        if self.series is None and (not self.categories or not self.values):
            raise ValueError(
                "categories and values are required for bar_categorical charts"
            )


@dataclass
class BoxSpec(ChartSpec):
    """Spec for box plots."""

    series: Sequence[dict[str, Any]] = ()
    orientation: Literal["vertical", "horizontal"] = "vertical"
    show_points: bool = False

    def validate(self) -> None:
        super().validate()
        if not self.series:
            raise ValueError("series is required for box_plot charts")


@dataclass
class NetworkGraphSpec(ChartSpec):
    """Spec for network graph charts."""

    nodes: Sequence[
        dict[str, Any]
    ] = ()  # List of node dicts with 'id', 'label', optionally 'size', 'color'
    edges: Sequence[
        dict[str, Any]
    ] = ()  # List of edge dicts with 'source', 'target', optionally 'weight', 'label'
    node_positions: dict[str, tuple[float, float]] | None = None

    def validate(self) -> None:
        super().validate()
        if not self.nodes:
            raise ValueError("nodes are required for network_graph charts")
        if not self.edges:
            raise ValueError("edges are required for network_graph charts")


@dataclass
class ScatterSeries:
    """Series definition for scatter charts."""

    name: str
    x: Sequence[Any]
    y: Sequence[Any]
    text: Sequence[str] | None = None
    marker: dict[str, Any] | None = None


@dataclass
class ScatterSpec(ChartSpec):
    """Spec for scatter charts (event timelines, point clouds)."""

    series: Sequence[ScatterSeries] | None = None
    x: Sequence[Any] = ()
    y: Sequence[Any] = ()
    text: Sequence[str] | None = None
    marker: dict[str, Any] | None = None
    mode: Literal["markers", "lines", "lines+markers"] = "markers"
    y_is_categorical: bool | None = None

    def get_series(self) -> list[ScatterSeries]:
        """Return normalized scatter series list."""
        if self.series:
            return list(self.series)
        if self.x and self.y:
            return [
                ScatterSeries(
                    name=self.name,
                    x=self.x,
                    y=self.y,
                    text=self.text,
                    marker=self.marker,
                )
            ]
        return []

    def validate(self) -> None:
        super().validate()
        if not self.get_series():
            raise ValueError("series or x/y is required for scatter charts")
