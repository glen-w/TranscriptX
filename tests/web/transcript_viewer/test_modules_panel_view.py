"""Tests for modules panel view."""

from __future__ import annotations

import transcriptx.web.transcript_viewer.modules_panel as mod


class _DummyCol:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _DummyExpander(_DummyCol):
    pass


def test_modules_panel_sets_selection(monkeypatch) -> None:
    state: dict = {}

    class _DummySt:
        session_state = state

        @staticmethod
        def divider():
            return None

        @staticmethod
        def subheader(*_args, **_kwargs):
            return None

        @staticmethod
        def info(*_args, **_kwargs):
            return None

        @staticmethod
        def selectbox(_label, options, index, format_func, key):
            state[key] = options[index]
            return options[index]

        @staticmethod
        def expander(*_args, **_kwargs):
            return _DummyExpander()

        @staticmethod
        def columns(n):
            return tuple(_DummyCol() for _ in range(max(n, 1)))

        @staticmethod
        def button(*_args, **_kwargs):
            return False

        @staticmethod
        def rerun():
            return None

    monkeypatch.setattr(mod, "st", _DummySt)
    monkeypatch.setattr(mod, "get_analysis_modules", lambda _selected: ["echoes"])
    monkeypatch.setattr(mod, "order_module_ids", lambda raw: raw)
    monkeypatch.setattr(
        mod, "group_modules_for_ui", lambda _raw: [("Core", ["echoes"])]
    )

    mod.render_modules_panel("slug/run1")
    assert state.get("analysis_module") == "echoes"
