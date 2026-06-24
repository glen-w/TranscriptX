"""Sidebar and Statistics navigation tests."""

from __future__ import annotations

from transcriptx.web.router import PAGE_PREREQUISITES, build_page_renderers


def test_statistics_in_page_prerequisites_and_renderers() -> None:
    assert "Statistics" in PAGE_PREREQUISITES
    renderers = build_page_renderers(
        corrections_studio_available=False,
        render_corrections_studio=None,
    )
    assert "Statistics" in renderers
    assert callable(renderers["Statistics"])


def test_view_page_sections_defined_in_sidebar_source() -> None:
    from pathlib import Path

    text = Path("src/transcriptx/web/sidebar.py").read_text(encoding="utf-8")
    assert "view_page_sections" in text
    assert '"Read"' in text
    assert '"Summarise"' in text
    assert '"Explore"' in text
    assert '_nav_button("Statistics", "Statistics")' in text
