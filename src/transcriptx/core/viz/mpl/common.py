"""Shared matplotlib renderer helpers."""

from __future__ import annotations

from typing import Any

from transcriptx.core.viz.specs import ChartSpec


def scatter_kwargs(marker: dict[str, Any] | None) -> dict[str, Any]:
    """Translate scatter marker config to matplotlib keyword arguments."""
    if not marker:
        return {}
    kwargs: dict[str, Any] = {}
    color = marker.get("color")
    if color is not None:
        kwargs["c"] = color
    size = marker.get("size")
    if size is not None:
        kwargs["s"] = size
    opacity = marker.get("opacity")
    if opacity is not None and not isinstance(opacity, list):
        kwargs["alpha"] = opacity
    symbol = marker.get("symbol")
    if isinstance(symbol, str):
        kwargs["marker"] = symbol
    return kwargs


def apply_axis_labels(ax: Any, spec: ChartSpec) -> None:
    """Apply chart title and axis labels."""
    ax.set_title(spec.title)
    if spec.x_label:
        ax.set_xlabel(spec.x_label)
    if spec.y_label:
        ax.set_ylabel(spec.y_label)


def draw_no_signal_overlay(ax: Any, message: str | None) -> None:
    """Draw standardized no-signal message above plot area."""
    if not message:
        return
    ax.text(
        0.5,
        1.02,
        message,
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=10,
        color="dimgray",
    )
