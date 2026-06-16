"""Heatmap matplotlib renderer."""

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
from transcriptx.core.viz.specs import HeatmapMatrixSpec


@register_probe(HeatmapMatrixSpec)
def heatmap_has_signal(spec: HeatmapMatrixSpec) -> bool:
    values: list[float] = []
    for row in spec.z:
        values.extend(coerce_floats(row))
    return bool(values) and any_nonzero(values)


@register(HeatmapMatrixSpec)
def render_heatmap(spec: HeatmapMatrixSpec, plt: Any) -> Any:
    fig, ax = plt.subplots(figsize=(8, 6))

    z_values: list[float] = []
    for row in spec.z:
        z_values.extend(coerce_floats(row))

    zmin = spec.zmin
    zmax = spec.zmax
    if z_values and zmin is None and zmax is None and min(z_values) == max(z_values):
        zmin = min(z_values)
        zmax = zmin + 1.0

    im = ax.imshow(spec.z, vmin=zmin, vmax=zmax, aspect="auto")
    apply_axis_labels(ax, spec)
    ax.set_xticks(range(len(spec.x_labels)))
    ax.set_xticklabels(spec.x_labels, rotation=45, ha="right")
    ax.set_yticks(range(len(spec.y_labels)))
    ax.set_yticklabels(spec.y_labels)
    draw_no_signal_overlay(ax, resolve_no_signal_message(spec))
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    return fig
