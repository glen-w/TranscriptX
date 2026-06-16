"""Line time-series matplotlib renderer."""

from __future__ import annotations

from typing import Any

from transcriptx.core.viz.mpl.common import apply_axis_labels, draw_no_signal_overlay
from transcriptx.core.viz.mpl.contracts import resolve_no_signal_message
from transcriptx.core.viz.mpl.dispatch import register
from transcriptx.core.viz.mpl.empty_signal import (
    any_nonzero,
    coerce_floats,
    register_probe,
)
from transcriptx.core.viz.specs import LineTimeSeriesSpec


@register_probe(LineTimeSeriesSpec)
def line_has_signal(spec: LineTimeSeriesSpec) -> bool:
    y_values: list[float] = []
    for series in spec.series:
        y_values.extend(coerce_floats(series.get("y", [])))
    return bool(y_values) and any_nonzero(y_values)


@register(LineTimeSeriesSpec)
def render_line(spec: LineTimeSeriesSpec, plt: Any) -> Any:
    fig, ax = plt.subplots(figsize=(10, 4))
    for series in spec.series:
        name = series.get("name", "")
        x_vals = series.get("x", [])
        y_vals = series.get("y", [])
        if spec.markers:
            ax.plot(x_vals, y_vals, marker="o", label=name)
        else:
            ax.plot(x_vals, y_vals, label=name)

    apply_axis_labels(ax, spec)
    ax.grid(True, alpha=0.3)
    draw_no_signal_overlay(ax, resolve_no_signal_message(spec))

    if any(series.get("name") for series in spec.series):
        ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5))
        fig.tight_layout(rect=[0, 0, 0.85, 1])
    else:
        fig.tight_layout()
    return fig
