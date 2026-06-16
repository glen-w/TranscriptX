"""Box-plot matplotlib renderer."""

from __future__ import annotations

from typing import Any

from transcriptx.core.viz.mpl.common import apply_axis_labels, draw_no_signal_overlay
from transcriptx.core.viz.mpl.contracts import (
    RenderContractError,
    resolve_no_signal_message,
    seeded_rng_for,
)
from transcriptx.core.viz.mpl.dispatch import register
from transcriptx.core.viz.mpl.empty_signal import (
    any_nonzero,
    coerce_floats,
    register_probe,
)
from transcriptx.core.viz.specs import BoxSpec


@register_probe(BoxSpec)
def box_has_signal(spec: BoxSpec) -> bool:
    values: list[float] = []
    for series in spec.series:
        values.extend(coerce_floats(series.get("y", [])))
    return bool(values) and any_nonzero(values)


@register(BoxSpec)
def render_box(spec: BoxSpec, plt: Any) -> Any:
    fig, ax = plt.subplots(figsize=(10, 4))
    series_list = list(spec.series)
    rng = seeded_rng_for(spec)

    has_x = [bool(series.get("x")) for series in series_list]
    if any(has_x) and not all(has_x):
        raise RenderContractError(
            "Box plot contract violation: either all series provide x or none do."
        )

    if all(has_x):
        box_categories: list[str] = []
        for series in series_list:
            for x_value in [str(x) for x in series.get("x", [])]:
                if x_value not in box_categories:
                    box_categories.append(x_value)
        base_positions = list(range(len(box_categories)))
        width = 0.8 / max(1, len(series_list))

        for idx, series in enumerate(series_list):
            xs = [str(x) for x in series.get("x", [])]
            ys = list(series.get("y", []))
            grouped: list[list[float]] = [[] for _ in box_categories]
            for x_value, y_value in zip(xs, ys):
                if x_value in box_categories:
                    grouped[box_categories.index(x_value)].append(y_value)

            filtered = [
                (cat, vals) for cat, vals in zip(box_categories, grouped) if vals
            ]
            if not filtered:
                continue

            positions = [
                base_positions[box_categories.index(cat)]
                + (idx - (len(series_list) - 1) / 2) * width
                for cat, _ in filtered
            ]
            ax.boxplot(
                [vals for _, vals in filtered],
                positions=positions,
                widths=width * 0.9,
                patch_artist=True,
                showfliers=True,
            )
            if spec.show_points:
                for pos, (_, vals) in zip(positions, filtered):
                    jitter = (rng.random(len(vals)) - 0.5) * width * 0.6
                    ax.scatter([pos + j for j in jitter], vals, alpha=0.6, s=10)

        ax.set_xticks(base_positions)
        ax.set_xticklabels(box_categories, rotation=30, ha="right")
    else:
        box_categories = [
            str(series.get("name", f"series_{idx}"))
            for idx, series in enumerate(series_list)
        ]
        base_positions = list(range(len(box_categories)))
        width = 0.8

        for idx, series in enumerate(series_list):
            vals = list(series.get("y", []))
            if vals:
                ax.boxplot(
                    [vals],
                    positions=[base_positions[idx]],
                    widths=width * 0.9,
                    patch_artist=True,
                    showfliers=True,
                )
            if spec.show_points and vals:
                jitter = (rng.random(len(vals)) - 0.5) * width * 0.6
                ax.scatter(
                    [base_positions[idx] + j for j in jitter], vals, alpha=0.6, s=10
                )

        ax.set_xticks(base_positions)
        ax.set_xticklabels(box_categories, rotation=30, ha="right")

    apply_axis_labels(ax, spec)
    draw_no_signal_overlay(ax, resolve_no_signal_message(spec))
    fig.tight_layout()
    return fig
