"""Tests for dashboard builder page (schema mode, no run)."""

from __future__ import annotations

from unittest.mock import MagicMock

import transcriptx.web.page_modules.dashboard_builder as mod
from transcriptx.web.blocks.builtin import register_builtin_blocks


def test_render_dashboard_builder_schema_mode_without_run(monkeypatch) -> None:
    calls: list[str] = []

    class _DummySt:
        session_state = {"active_layout_profile_id": "default"}

        @staticmethod
        def selectbox(label, options, **kwargs):
            if label == "Layout profile":
                return "default"
            return options[0] if options else ""

        @staticmethod
        def radio(label, options, **kwargs):
            return "Schema"

        @staticmethod
        def subheader(text):
            calls.append(f"sub:{text}")

        @staticmethod
        def expander(title, expanded=False):
            return MagicMock(__enter__=lambda s: s, __exit__=lambda *a: None)

        @staticmethod
        def markdown(*args, **kwargs):
            calls.append("markdown")

        @staticmethod
        def caption(text):
            calls.append(f"cap:{text}")

        @staticmethod
        def write(*args, **kwargs):
            calls.append("write")

        @staticmethod
        def code(*args, **kwargs):
            calls.append("code")

        @staticmethod
        def success(msg):
            calls.append(f"ok:{msg}")

        @staticmethod
        def error(msg):
            calls.append(f"err:{msg}")

    monkeypatch.setattr(mod, "st", _DummySt)
    monkeypatch.setattr(mod, "render_page_shell", lambda *a, **k: None)
    monkeypatch.setattr(mod, "render_page_help", lambda _h: None)
    register_builtin_blocks()

    mod.render_dashboard_builder()
    assert any("Registered blocks" in c for c in calls)
    assert any(c.startswith("ok:") for c in calls)
