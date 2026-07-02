from __future__ import annotations

from unittest.mock import MagicMock

from transcriptx.web.router import (
    PAGE_PREREQUISITES,
    build_page_renderers,
    fallback_for_page,
)


def test_fallback_for_page_known() -> None:
    assert fallback_for_page("Overview") == "Home"
    assert fallback_for_page("Charts") == "Overview"


def test_build_page_renderers_contains_core_pages() -> None:
    renderers = build_page_renderers(
        corrections_studio_available=False,
        render_corrections_studio=None,
    )
    optional_without_renderer = {"Corrections Studio"}
    for key in PAGE_PREREQUISITES:
        if key in optional_without_renderer:
            continue
        assert key in renderers


def test_build_page_renderers_includes_corrections_studio_when_available() -> None:
    stub = MagicMock()
    renderers = build_page_renderers(
        corrections_studio_available=True,
        render_corrections_studio=stub,
    )
    assert "Corrections Studio" in renderers
    assert renderers["Corrections Studio"] is stub
