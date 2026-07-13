"""Sidebar and Statistics navigation tests."""

from __future__ import annotations

from pathlib import Path

from transcriptx.web.navigation import PAGE_SPECS, get_page_spec
from transcriptx.web.router import PAGE_PREREQUISITES, build_page_renderers


def test_statistics_in_page_prerequisites_and_renderers() -> None:
    assert "Statistics" in PAGE_PREREQUISITES
    renderers = build_page_renderers(
        corrections_studio_available=False,
        render_corrections_studio=None,
    )
    assert "Statistics" in renderers
    assert callable(renderers["Statistics"])


def test_statistics_required_context_is_none() -> None:
    spec = get_page_spec("Statistics")
    assert spec.required_context == "none"
    assert spec.section == "view"


def test_view_pages_use_flat_nav_grouping() -> None:
    # Legacy Data/Explorer keep subsection="legacy" for redirect aliases but are
    # excluded from sidebar via pages_in_section().
    subsections = {
        spec.subsection
        for spec in PAGE_SPECS
        if spec.section == "view" and spec.subsection
    }
    assert subsections <= {"legacy"}
    from transcriptx.web.navigation import pages_in_section

    assert all(s.subsection is None for s in pages_in_section("view"))


def test_sidebar_uses_registry_driven_view_sections() -> None:
    text = Path("src/transcriptx/web/sidebar.py").read_text(encoding="utf-8")
    assert "pages_in_section" in text
    assert 'pages_in_section("view")' in text
    assert "_VIEW_SUBSECTION_ORDER" not in text
