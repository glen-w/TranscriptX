"""Tests for dashboard builder page (schema mode, no run)."""

from __future__ import annotations

from unittest.mock import MagicMock

import transcriptx.web.page_modules.dashboard_builder as mod
from transcriptx.web.blocks.builtin import register_builtin_blocks
from transcriptx.web.layouts.store import LayoutProfileStore, LayoutValidationError


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

        @staticmethod
        def info(msg):
            calls.append(f"info:{msg}")

        @staticmethod
        def text_input(label, value="", **kwargs):
            return value

        @staticmethod
        def button(label, **kwargs):
            return False

        @staticmethod
        def checkbox(label, value=False, **kwargs):
            return value

    monkeypatch.setattr(mod, "st", _DummySt)
    monkeypatch.setattr(mod, "render_page_shell", lambda *a, **k: None)
    register_builtin_blocks()

    mod.render_dashboard_builder()
    assert any("Registered blocks" in c for c in calls)
    assert any(c.startswith("ok:") for c in calls)
    assert _DummySt.session_state.get("show_debug_layouts") is True


def test_save_as_custom_requires_overwrite_confirm(monkeypatch, tmp_path) -> None:
    register_builtin_blocks()
    source = LayoutProfileStore.load_layout("minimal")
    LayoutProfileStore.save_as_custom(source, "taken", base=tmp_path)
    errors: list[str] = []
    saved: list[str] = []

    class _DummySt:
        session_state = {"active_layout_profile_id": "minimal"}

        @staticmethod
        def selectbox(label, options, **kwargs):
            return "minimal"

        @staticmethod
        def radio(label, options, **kwargs):
            return "Schema"

        @staticmethod
        def subheader(text):
            return None

        @staticmethod
        def expander(title, expanded=False):
            return MagicMock(__enter__=lambda s: s, __exit__=lambda *a: None)

        @staticmethod
        def markdown(*args, **kwargs):
            return None

        @staticmethod
        def caption(text):
            return None

        @staticmethod
        def write(*args, **kwargs):
            return None

        @staticmethod
        def code(*args, **kwargs):
            return None

        @staticmethod
        def success(msg):
            return None

        @staticmethod
        def error(msg):
            errors.append(str(msg))

        @staticmethod
        def info(msg):
            return None

        @staticmethod
        def text_input(label, value="", **kwargs):
            if label == "New layout id":
                return "taken"
            return value

        @staticmethod
        def button(label, **kwargs):
            return label == "Save as custom layout"

        @staticmethod
        def checkbox(label, value=False, **kwargs):
            return False

        @staticmethod
        def rerun():
            raise AssertionError("should not rerun when overwrite blocked")

    monkeypatch.setattr(mod, "st", _DummySt)
    monkeypatch.setattr(mod, "render_page_shell", lambda *a, **k: None)
    monkeypatch.setattr(mod, "render_layout_profile_picker", lambda **k: None)
    monkeypatch.setattr(
        LayoutProfileStore,
        "custom_layout_exists",
        staticmethod(lambda layout_id, base=None: layout_id == "taken"),
    )

    def _save_as_custom(
        source_layout, new_id, *, title=None, base=None, overwrite=True
    ):
        if not overwrite:
            raise LayoutValidationError(
                f"Custom layout '{new_id}' already exists. Pass overwrite=True to replace it."
            )
        saved.append(new_id)
        return tmp_path / f"{new_id}.yaml"

    monkeypatch.setattr(
        LayoutProfileStore, "save_as_custom", staticmethod(_save_as_custom)
    )

    mod.render_dashboard_builder()
    assert saved == []
    assert any("already exists" in e for e in errors)


def test_preview_mode_loads_selected_layout(monkeypatch) -> None:
    """Preview must load the chosen layout id (not the session default)."""
    register_builtin_blocks()
    loaded: list[str] = []
    rendered: list[tuple[str, object]] = []

    class _DummySt:
        session_state = {
            "active_layout_profile_id": "default",
            "current_run_path": "/tmp/fake-run",
        }

        @staticmethod
        def selectbox(label, options, **kwargs):
            if label == "Preview page":
                return options[0] if options else ""
            return options[0] if options else ""

        @staticmethod
        def radio(label, options, **kwargs):
            return "Preview"

        @staticmethod
        def subheader(text):
            return None

        @staticmethod
        def expander(title, expanded=False):
            return MagicMock(__enter__=lambda s: s, __exit__=lambda *a: None)

        @staticmethod
        def markdown(*args, **kwargs):
            return None

        @staticmethod
        def caption(text):
            return None

        @staticmethod
        def write(*args, **kwargs):
            return None

        @staticmethod
        def code(*args, **kwargs):
            return None

        @staticmethod
        def success(msg):
            return None

        @staticmethod
        def error(msg):
            return None

        @staticmethod
        def info(msg):
            return None

        @staticmethod
        def text_input(label, value="", **kwargs):
            return value

        @staticmethod
        def button(label, **kwargs):
            return False

        @staticmethod
        def checkbox(label, value=False, **kwargs):
            return value

        @staticmethod
        def warning(msg):
            return None

    monkeypatch.setattr(mod, "st", _DummySt)
    monkeypatch.setattr(mod, "render_page_shell", lambda *a, **k: None)
    monkeypatch.setattr(mod, "render_layout_profile_picker", lambda **k: None)
    monkeypatch.setattr(mod, "active_layout_id", lambda: "meeting_followup")
    monkeypatch.setattr(
        mod,
        "build_context_from_session",
        lambda session_state, layout_profile_id=None: MagicMock(
            layout_profile_id=layout_profile_id,
            run_dir="/tmp/fake-run",
        ),
    )

    real_load = LayoutProfileStore.load_layout

    def _tracking_load(layout_id, base=None):
        loaded.append(layout_id)
        return real_load(layout_id, base=base)

    monkeypatch.setattr(LayoutProfileStore, "load_layout", staticmethod(_tracking_load))
    monkeypatch.setattr(
        mod,
        "render_layout_page",
        lambda page, ctx, layout: rendered.append((page, layout.id)),
    )

    mod.render_dashboard_builder()
    assert "meeting_followup" in loaded
    assert rendered
    assert all(layout_id == "meeting_followup" for _page, layout_id in rendered)


def test_edit_mode_renders_layout_editor(monkeypatch) -> None:
    register_builtin_blocks()
    editor_calls: list[str] = []

    class _DummySt:
        session_state = {"active_layout_profile_id": "default"}

        @staticmethod
        def selectbox(label, options, **kwargs):
            return options[0] if options else ""

        @staticmethod
        def radio(label, options, **kwargs):
            return "Edit"

        @staticmethod
        def info(msg):
            return None

        @staticmethod
        def error(msg):
            return None

    monkeypatch.setattr(mod, "st", _DummySt)
    monkeypatch.setattr(mod, "render_page_shell", lambda *a, **k: None)
    monkeypatch.setattr(mod, "render_layout_profile_picker", lambda **k: None)
    monkeypatch.setattr(
        mod,
        "render_layout_editor",
        lambda layout_id: editor_calls.append(layout_id),
    )

    mod.render_dashboard_builder()
    assert editor_calls == ["default"]
