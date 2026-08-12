"""Tests for Charts overview checkbox selector helpers."""

from __future__ import annotations

from transcriptx.core.utils.chart_registry import get_default_overview_charts
from transcriptx.web.ui.settings.charts_overview_selector import (
    OVERVIEW_CHARTS_KEY,
    move_overview_chart,
    normalize_overview_selection,
    toggle_overview_chart,
)


def test_normalize_overview_selection() -> None:
    assert normalize_overview_selection(None) == []
    assert normalize_overview_selection([]) == []
    assert normalize_overview_selection(["a", "a", "b"]) == ["a", "b"]
    assert normalize_overview_selection("solo") == ["solo"]


def test_toggle_and_move_overview_chart() -> None:
    selected = toggle_overview_chart([], "a", enabled=True)
    selected = toggle_overview_chart(selected, "b", enabled=True)
    assert selected == ["a", "b"]
    selected = toggle_overview_chart(selected, "a", enabled=False)
    assert selected == ["b"]
    selected = ["x", "y", "z"]
    assert move_overview_chart(selected, 1, -1) == ["y", "x", "z"]
    assert move_overview_chart(selected, 0, -1) == ["x", "y", "z"]


def test_default_overview_charts_nonempty() -> None:
    defaults = get_default_overview_charts()
    assert defaults
    assert OVERVIEW_CHARTS_KEY == "dashboard.overview_charts"
