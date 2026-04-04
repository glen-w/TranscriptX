"""Utilities for chart axis formatting."""

from __future__ import annotations

from typing import List

# Threshold above which we show time in hours instead of minutes (1 hour)
TIME_AXIS_HOURS_THRESHOLD_SEC = 3600.0


def time_axis_display(time_values_seconds: List[float]) -> tuple[List[float], str]:
    """Convert time axis from seconds to minutes or hours for better readability.

    - Short transcripts (≤1 hour): axis in minutes.
    - Longer transcripts: axis in hours (e.g. 1, 1.5, 2, 2.5).
    Returns (x_values_display, x_label).
    """
    if not time_values_seconds:
        return [], "Time (minutes)"
    max_sec = max(time_values_seconds)
    if max_sec <= TIME_AXIS_HOURS_THRESHOLD_SEC:
        x_display = [t / 60.0 for t in time_values_seconds]
        return x_display, "Time (minutes)"
    x_display = [t / 3600.0 for t in time_values_seconds]
    return x_display, "Time (hours)"
