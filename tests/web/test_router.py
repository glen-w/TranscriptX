"""Tests for router."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from transcriptx.web.navigation import LEGACY_PAGE_REDIRECTS, migrate_legacy_page_key
from transcriptx.web.router import (
    PAGE_PREREQUISITES,
    build_page_renderers,
    fallback_for_page,
)
from transcriptx.web.state import PAGE_KEY


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


@pytest.mark.unit
def test_batch_ops_not_in_legacy_page_redirects() -> None:
    assert "Batch Ops" not in LEGACY_PAGE_REDIRECTS
    assert "Data" not in LEGACY_PAGE_REDIRECTS
    assert "Explorer" not in LEGACY_PAGE_REDIRECTS
    assert migrate_legacy_page_key("Batch Ops") == ("Batch Ops", None)


@pytest.mark.unit
def test_data_and_explorer_not_in_renderers() -> None:
    renderers = build_page_renderers(
        corrections_studio_available=False,
        render_corrections_studio=None,
    )
    assert "Data" not in renderers
    assert "Explorer" not in renderers
    assert "Data" not in PAGE_PREREQUISITES
    assert "Explorer" not in PAGE_PREREQUISITES


@pytest.mark.unit
def test_redirect_legacy_batch_ops_presets_batch_target(monkeypatch) -> None:
    import transcriptx.web.router as router

    ss: dict = {PAGE_KEY: "Batch Ops", "run_analysis_target": "Transcript"}
    rendered: list[bool] = []

    class _St:
        session_state = ss

    monkeypatch.setattr(router, "st", _St)
    monkeypatch.setattr(
        "transcriptx.web.page_modules.run_analysis.render_run_analysis_page",
        lambda: rendered.append(True),
    )

    router._redirect_legacy_batch_ops()

    assert ss[PAGE_KEY] == "Run Analysis"
    assert ss["run_analysis_target"] == "Batch"
    assert rendered == [True]


@pytest.mark.unit
def test_build_page_renderers_includes_tools() -> None:
    renderers = build_page_renderers(
        corrections_studio_available=False,
        render_corrections_studio=None,
    )
    assert "Tools" in renderers
    assert "Tools" in PAGE_PREREQUISITES


@pytest.mark.unit
def test_legacy_audio_prep_redirect_sets_tools_tab(monkeypatch) -> None:
    import transcriptx.web.router as router
    from transcriptx.web.navigation import (
        TOOLS_HUB_FORCE_TAB_KEY,
        TOOLS_HUB_TAB_KEY,
    )

    ss: dict = {PAGE_KEY: "Audio Merge"}
    rendered: list[str] = []

    class _St:
        session_state = ss
        warning = staticmethod(lambda *_a, **_k: None)

    monkeypatch.setattr(router, "st", _St)
    monkeypatch.setattr(
        router,
        "build_page_renderers",
        lambda **_k: {"Tools": lambda: rendered.append("tools")},
    )
    monkeypatch.setattr(
        router,
        "context_readiness",
        lambda *_a, **_k: MagicMock(),
    )
    monkeypatch.setattr(
        router,
        "evaluate_page_access",
        lambda *_a, **_k: MagicMock(allowed=True),
    )

    router.route_current_page(
        ss,
        corrections_studio_available=False,
        render_corrections_studio=None,
    )

    assert ss[PAGE_KEY] == "Tools"
    assert ss[TOOLS_HUB_TAB_KEY] == "Auto-merge"
    assert ss[TOOLS_HUB_FORCE_TAB_KEY] == "Auto-merge"
    assert rendered == ["tools"]


@pytest.mark.unit
def test_run_analysis_batch_ops_import_cycle_safe() -> None:
    """batch_ops must not import run_analysis; router may import run_analysis locally."""
    import transcriptx.web.page_modules.batch_ops as batch_ops
    import transcriptx.web.page_modules.run_analysis as run_analysis
    import transcriptx.web.router as router

    assert hasattr(batch_ops, "render_batch_analysis_panel")
    assert hasattr(run_analysis, "render_run_analysis_page")
    assert "Batch Ops" in build_page_renderers(
        corrections_studio_available=False,
        render_corrections_studio=None,
    )
    assert callable(router._redirect_legacy_batch_ops)
