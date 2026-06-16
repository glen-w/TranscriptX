"""Categorical bar matplotlib renderer."""

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
from transcriptx.core.viz.specs import BarCategoricalSpec


@register_probe(BarCategoricalSpec)
def bar_has_signal(spec: BarCategoricalSpec) -> bool:
    if spec.series is None:
        values = coerce_floats(spec.values)
        return bool(values) and any_nonzero(values)
    if len(spec.series) == 0:
        return False
    values: list[float] = []
    for series in spec.series:
        values.extend(coerce_floats(series.get("values", [])))
    return bool(values) and any_nonzero(values)


@register(BarCategoricalSpec)
def render_bar(spec: BarCategoricalSpec, plt: Any) -> Any:
    fig, ax = plt.subplots(figsize=(8, 4))

    if spec.series is None:
        if spec.orientation == "horizontal":
            ax.barh(spec.categories, spec.values)
        else:
            ax.bar(spec.categories, spec.values)
            ax.set_xticks(range(len(spec.categories)))
            ax.set_xticklabels(spec.categories, rotation=30, ha="right")
    else:
        n_series = len(spec.series)
        width = 0.8 / max(1, n_series)
        bar_categories: list[str] = []

        for series in spec.series:
            categories = series.get("categories") or ()
            if categories:
                bar_categories = [str(c) for c in categories]
                break
        if not bar_categories and spec.categories:
            bar_categories = [str(c) for c in spec.categories]

        for idx, series in enumerate(spec.series):
            categories = series.get("categories", bar_categories) or spec.categories
            values = series.get("values", [])
            positions = [i + idx * width for i in range(len(categories))]
            if spec.orientation == "horizontal":
                ax.barh(positions, values, height=width, label=series.get("name"))
            else:
                ax.bar(positions, values, width=width, label=series.get("name"))

        if any(series.get("name") for series in spec.series):
            ax.legend()

        if bar_categories:
            if n_series == 0:
                tick_centers = [float(i) for i in range(len(bar_categories))]
            else:
                tick_centers = [
                    float(i) + (n_series - 1) * width / 2.0
                    for i in range(len(bar_categories))
                ]
            if spec.orientation == "horizontal":
                ax.set_yticks(tick_centers)
                ax.set_yticklabels(bar_categories)
            else:
                ax.set_xticks(tick_centers)
                ax.set_xticklabels(bar_categories, rotation=30, ha="right")

    apply_axis_labels(ax, spec)
    draw_no_signal_overlay(ax, resolve_no_signal_message(spec))
    fig.tight_layout()
    return fig
