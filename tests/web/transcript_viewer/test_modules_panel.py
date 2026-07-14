"""Tests for modules panel."""

from __future__ import annotations

from transcriptx.web.transcript_viewer.modules_panel import build_module_panel_layout


def test_build_module_panel_layout_empty() -> None:
    layout = build_module_panel_layout([])
    assert layout.flat == []
    assert layout.groups == []
    assert layout.ungrouped == []
