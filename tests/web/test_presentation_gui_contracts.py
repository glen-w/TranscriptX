"""High-leverage GUI presentation + demo UI contracts (offline)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from transcriptx.web.presentation.guided_settings import GUIDED_SETTINGS_SCHEMA
from transcriptx.web.presentation.prefs import MODE_FULL, MODE_GUIDED
from transcriptx.web.presentation.resolve import MODE_LABELS, set_presentation_mode
from transcriptx.web.presentation.seed import workspace_looks_existing
from transcriptx.web.presentation.visibility import (
    GUIDED_SETTINGS_TABS,
    page_visible_in_presentation,
    visible_pages_in_section,
)


@pytest.mark.unit
def test_mode_labels_locked() -> None:
    assert MODE_LABELS[MODE_GUIDED] == "Guided"
    assert MODE_LABELS[MODE_FULL] == "Full controls"


@pytest.mark.unit
def test_guided_settings_schema_keys_are_approachable() -> None:
    keys = [item.key for item in GUIDED_SETTINGS_SCHEMA]
    assert keys
    assert all("." in k for k in keys)
    assert GUIDED_SETTINGS_TABS == (
        "Configuration",
        "Analysis",
        "Storage",
        "Speakers",
    )


@pytest.mark.unit
def test_visible_pages_primary_always_includes_home() -> None:
    pages = visible_pages_in_section("primary", MODE_GUIDED)
    assert any(p.key == "Home" for p in pages)
    assert page_visible_in_presentation("Library", MODE_GUIDED)


@pytest.mark.unit
def test_workspace_existing_via_outputs_dir(tmp_path: Path) -> None:
    cfg = tmp_path / "cfg"
    out = tmp_path / "out"
    cfg.mkdir()
    out.mkdir()
    (out / "some_slug").mkdir()
    assert workspace_looks_existing(config_dir=cfg, outputs_dir=out) is True


@pytest.mark.unit
def test_set_presentation_mode_rejects_unknown() -> None:
    result = set_presentation_mode("not-a-mode")
    assert result.ok is False
    assert "Unknown" in (result.error or "")


@pytest.mark.unit
def test_demo_ui_helpers_importable() -> None:
    from transcriptx.web import demo_ui

    assert callable(demo_ui.render_home_demo_and_onboarding)
    assert callable(demo_ui.render_settings_demo_controls)


@pytest.mark.unit
def test_settings_demo_toggle_installs_when_on(monkeypatch) -> None:
    from tests.web.streamlit_doubles import DummyHomeStreamlit
    from transcriptx.demo import DemoStatusKind
    from transcriptx.web import demo_ui

    session: dict = {}
    DummyHomeStreamlit.session_state = session
    installs: list[str] = []
    reruns: list[str] = []

    class _Status:
        kind = DemoStatusKind.MISSING
        detail = "missing"

    class _St(DummyHomeStreamlit):
        session_state = session

        @staticmethod
        def expander(*_a, **_k):
            from tests.web.streamlit_doubles import DummyExpander

            return DummyExpander()

        @staticmethod
        def toggle(*_a, **_k):
            return True

        @staticmethod
        def spinner(*_a, **_k):
            from contextlib import nullcontext

            return nullcontext()

        @staticmethod
        def rerun():
            reruns.append("rerun")

        @staticmethod
        def button(*_a, **_k):
            return False

    monkeypatch.setattr(demo_ui, "st", _St)
    monkeypatch.setattr(demo_ui, "status_demo_project", lambda: _Status())
    monkeypatch.setattr(
        demo_ui,
        "install_demo_project",
        lambda: (
            installs.append("install")
            or type("R", (), {"ok": True, "detail": "ok", "errors": []})()
        ),
    )
    demo_ui.render_settings_demo_controls()
    assert installs == ["install"]
    assert "rerun" in reruns


@pytest.mark.unit
def test_unlock_banner_calls_set_mode(monkeypatch) -> None:
    from transcriptx.web.presentation import visibility as vis

    calls: list[str] = []
    seen: list[str] = []

    class _St:
        @staticmethod
        def warning(*_a, **_k):
            return None

        @staticmethod
        def caption(*_a, **_k):
            return None

        @staticmethod
        def button(*_a, **_k):
            return True

        @staticmethod
        def rerun():
            calls.append("rerun")

        @staticmethod
        def error(*_a, **_k):
            return None

    def _set(mode):
        seen.append(mode)
        return MagicMock(ok=True)

    monkeypatch.setattr(vis, "set_presentation_mode", _set)
    monkeypatch.setitem(__import__("sys").modules, "streamlit", _St)
    # Function imports streamlit locally — patch the module attribute used after import.
    import streamlit as real_st

    monkeypatch.setattr(real_st, "warning", _St.warning)
    monkeypatch.setattr(real_st, "caption", _St.caption)
    monkeypatch.setattr(real_st, "button", _St.button)
    monkeypatch.setattr(real_st, "rerun", _St.rerun)
    monkeypatch.setattr(real_st, "error", _St.error)
    vis.render_full_only_unlock_banner("Audio Prep")
    assert seen == [MODE_FULL]
    assert "rerun" in calls
