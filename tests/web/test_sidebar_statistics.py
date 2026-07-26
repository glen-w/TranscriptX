"""Sidebar view-section navigation tests."""

from __future__ import annotations

from pathlib import Path

from transcriptx.web.navigation import PAGE_SPECS, migrate_legacy_page_key
from transcriptx.web.router import PAGE_PREREQUISITES, build_page_renderers


def test_statistics_page_removed_from_nav_and_renderers() -> None:
    assert "Statistics" not in PAGE_PREREQUISITES
    assert all(spec.key != "Statistics" for spec in PAGE_SPECS)
    renderers = build_page_renderers(
        corrections_studio_available=False,
        render_corrections_studio=None,
    )
    assert "Statistics" not in renderers
    assert migrate_legacy_page_key("Statistics") == ("Home", None)


def test_view_pages_use_flat_nav_grouping() -> None:
    # View section is flat; only Batch Ops (workflow) retains subsection="legacy".
    subsections = {
        spec.subsection
        for spec in PAGE_SPECS
        if spec.section == "view" and spec.subsection
    }
    assert subsections == set()
    from transcriptx.web.navigation import pages_in_section

    assert all(s.subsection is None for s in pages_in_section("view"))


def test_sidebar_uses_registry_driven_view_sections() -> None:
    text = Path("src/transcriptx/web/sidebar.py").read_text(encoding="utf-8")
    assert "pages_in_section" in text
    assert 'pages_in_section("view")' in text
    assert "_VIEW_SUBSECTION_ORDER" not in text