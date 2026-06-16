"""Scatter matplotlib renderer."""

from __future__ import annotations

from typing import Any

from transcriptx.core.viz.mpl.common import (
    apply_axis_labels,
    draw_no_signal_overlay,
    scatter_kwargs,
)
from transcriptx.core.viz.mpl.contracts import resolve_no_signal_message
from transcriptx.core.viz.mpl.dispatch import register
from transcriptx.core.viz.mpl.empty_signal import (
    any_nonzero,
    coerce_floats,
    register_probe,
)
from transcriptx.core.viz.specs import ScatterSpec


@register_probe(ScatterSpec)
def scatter_has_signal(spec: ScatterSpec) -> bool:
    y_values: list[float] = []
    for series in spec.get_series():
        y_values.extend(coerce_floats(series.y))
    return bool(y_values) and any_nonzero(y_values)


@register(ScatterSpec)
def render_scatter(spec: ScatterSpec, plt: Any) -> Any:
    fig, ax = plt.subplots(figsize=(10, 4))
    series_list = spec.get_series()

    for series in series_list:
        marker = series.marker or {}
        marker_kwargs = scatter_kwargs(marker)
        if spec.mode in ("markers", "lines+markers"):
            ax.scatter(series.x, series.y, label=series.name or None, **marker_kwargs)
        if spec.mode in ("lines", "lines+markers"):
            line_kwargs: dict[str, Any] = {}
            color = marker.get("color")
            if isinstance(color, str):
                line_kwargs["color"] = color
            ax.plot(series.x, series.y, **line_kwargs)

    apply_axis_labels(ax, spec)
    if any(series.name for series in series_list):
        ax.legend()
    ax.grid(True, alpha=0.3)
    draw_no_signal_overlay(ax, resolve_no_signal_message(spec))
    fig.tight_layout()
    return fig
