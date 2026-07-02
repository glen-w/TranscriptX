from __future__ import annotations

from datetime import datetime
from pathlib import Path

from tests.web.streamlit_doubles import DummyHomeStreamlit


def test_home_initial_render_skips_workspace_summary_and_transcript_listing(
    monkeypatch,
) -> None:
    import transcriptx.web.page_modules.home as mod

    DummyHomeStreamlit.session_state = {}
    monkeypatch.setattr(mod, "st", DummyHomeStreamlit)
    monkeypatch.setattr(mod, "render_page_shell", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(mod, "render_page_help", lambda *_args, **_kwargs: None)
    slug_label_calls = {"count": 0}
    monkeypatch.setattr(
        mod,
        "_slug_display_labels_from_index",
        lambda: slug_label_calls.__setitem__("count", slug_label_calls["count"] + 1)
        or {},
    )
    monkeypatch.setattr(Path, "exists", lambda _self: True)
    calls = {"recent_runs": 0, "groups": 0, "transcripts": 0}

    class _Run:
        created_at = datetime(2026, 3, 25, 10, 0)
        run_id = "run-1"
        run_dir = Path("/tmp/slug-1/run-1")
        transcript_path = Path("/tmp/slug-1.json")
        selected_modules = ["overview"]

    def _fake_instrument(name, fn, *args, **kwargs):
        if name == "cached_list_recent_runs":
            calls["recent_runs"] += 1
            return [_Run()]
        if name == "cached_list_groups":
            calls["groups"] += 1
            return []
        if name == "cached_list_transcripts":
            calls["transcripts"] += 1
            return []
        return fn(*args, **kwargs)

    monkeypatch.setattr(mod, "instrument_cached_call", _fake_instrument)

    mod.render_home()

    assert calls["recent_runs"] == 1
    assert calls["groups"] == 0
    assert calls["transcripts"] == 0
    assert slug_label_calls["count"] == 1


def test_home_skips_slug_labels_when_no_recent_runs(monkeypatch) -> None:
    import transcriptx.web.page_modules.home as mod

    DummyHomeStreamlit.session_state = {}
    monkeypatch.setattr(mod, "st", DummyHomeStreamlit)
    monkeypatch.setattr(mod, "render_page_shell", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(mod, "render_page_help", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(mod, "render_empty_state", lambda *_args, **_kwargs: None)
    slug_label_calls = {"count": 0}
    monkeypatch.setattr(
        mod,
        "_slug_display_labels_from_index",
        lambda: slug_label_calls.__setitem__("count", slug_label_calls["count"] + 1)
        or {},
    )
    monkeypatch.setattr(Path, "exists", lambda _self: True)

    def _fake_instrument(name, fn, *args, **kwargs):
        if name == "cached_list_recent_runs":
            return []
        return fn(*args, **kwargs)

    monkeypatch.setattr(mod, "instrument_cached_call", _fake_instrument)

    mod.render_home()

    assert slug_label_calls["count"] == 0


def test_home_workspace_summary_button_loads_groups(monkeypatch) -> None:
    import transcriptx.web.page_modules.home as mod

    DummyHomeStreamlit.session_state = {}
    monkeypatch.setattr(mod, "st", DummyHomeStreamlit)
    monkeypatch.setattr(mod, "render_page_shell", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(mod, "render_page_help", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(mod, "_slug_display_labels_from_index", lambda: {})
    monkeypatch.setattr(Path, "exists", lambda _self: True)
    calls = {"groups": 0}

    class _Run:
        created_at = datetime(2026, 3, 25, 10, 0)
        run_id = "run-1"
        run_dir = Path("/tmp/slug-1/run-1")
        transcript_path = Path("/tmp/slug-1.json")
        selected_modules = ["overview"]

    def _fake_instrument(name, fn, *args, **kwargs):
        if name == "cached_list_recent_runs":
            return [_Run()]
        if name == "cached_list_groups":
            calls["groups"] += 1
            return []
        return fn(*args, **kwargs)

    monkeypatch.setattr(mod, "instrument_cached_call", _fake_instrument)

    class _ButtonHomeStreamlit(DummyHomeStreamlit):
        @staticmethod
        def button(*_args, key=None, **_kwargs):
            return key == "home_load_workspace_summary"

    monkeypatch.setattr(mod, "st", _ButtonHomeStreamlit)
    mod.render_home()
    assert (
        _ButtonHomeStreamlit.session_state.get("home_workspace_summary_requested")
        is True
    )

    class _PlainHomeStreamlit(DummyHomeStreamlit):
        @staticmethod
        def button(*_args, **_kwargs):
            return False

    monkeypatch.setattr(mod, "st", _PlainHomeStreamlit)
    mod.render_home()
    assert calls["groups"] == 1
