"""
Helpers to render compact intensity lines in Markdown.
"""

from __future__ import annotations

from typing import Iterable, Tuple


def bucket(
    value: float | None,
    thresholds: Tuple[float, float] = (0.33, 0.66),
    labels: Tuple[str, str, str] = ("low", "medium", "high"),
) -> str:
    if value is None:
        return "unknown"
    if value < thresholds[0]:
        return labels[0]
    if value < thresholds[1]:
        return labels[1]
    return labels[2]


def render_intensity_line(
    title: str,
    value: float | None,
    *,
    label: str | None = None,
    extra: str | None = None,
) -> str:
    resolved_label = label or bucket(value)
    value_text = "n/a" if value is None else f"{value:.2f}"
    extra_text = f" {extra}" if extra else ""
    return f"**{title} intensity:** {resolved_label} ({value_text}){extra_text}"
