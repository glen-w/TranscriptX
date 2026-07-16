"""Tests for app startup."""

from __future__ import annotations

from transcriptx.web.state import PAGE_KEY
from tests.web.streamlit_doubles import DummySidebar, DummyStreamlit

_LEGACY_TRANSCRIPT_PATH_KEY = "selected_transcript_path"


def test_init_defaults_purges_legacy_transcript_path(monkeypatch) -> None:
    import transcriptx.web.app as mod

    dummy_st = DummyStreamlit()
    dummy_st.session_state = {_LEGACY_TRANSCRIPT_PATH_KEY: "/tmp/a.json"}
    monkeypatch.setattr(mod, "st", dummy_st)

    mod._init_defaults()

    assert _LEGACY_TRANSCRIPT_PATH_KEY not in dummy_st.session_state


def test_home_cold_render_skips_session_discovery(monkeypatch) -> None:
    import transcriptx.web.app as mod

    dummy_st = DummyStreamlit()
    monkeypatch.setattr(mod, "st", dummy_st)
    monkeypatch.setattr(mod, "start_run", lambda **_kwargs: "run-1")
    monkeypatch.setattr(mod, "record_elapsed_section", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(mod, "finish_run", lambda **_kwargs: None)
    monkeypatch.setattr(mod, "consume_page_flash", lambda: None)
    context_calls = {"n": 0}
    monkeypatch.setattr(
        mod,
        "render_context_bar",
        lambda _ss: context_calls.__setitem__("n", context_calls["n"] + 1),
    )
    monkeypatch.setattr(mod, "route_current_page", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(mod, "render_sidebar", lambda **_kwargs: None)
    monkeypatch.setattr(mod, "section", lambda *_args, **_kwargs: DummySidebar())
    called = {"sessions": 0}
    monkeypatch.setattr(
        mod,
        "instrument_cached_call",
        lambda *_args, **_kwargs: called.__setitem__(
            "sessions", called["sessions"] + 1
        ),
    )

    mod.main()

    assert called["sessions"] == 0
    assert context_calls["n"] == 0


def test_charts_page_triggers_session_discovery(monkeypatch) -> None:
    import transcriptx.web.app as mod

    dummy_st = DummyStreamlit()
    dummy_st.session_state = {PAGE_KEY: "Charts"}
    monkeypatch.setattr(mod, "st", dummy_st)
    monkeypatch.setattr(mod, "start_run", lambda **_kwargs: "run-1")
    monkeypatch.setattr(mod, "record_elapsed_section", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(mod, "finish_run", lambda **_kwargs: None)
    monkeypatch.setattr(mod, "consume_page_flash", lambda: None)
    context_calls = {"n": 0}
    monkeypatch.setattr(
        mod,
        "render_context_bar",
        lambda _ss: context_calls.__setitem__("n", context_calls["n"] + 1),
    )
    monkeypatch.setattr(mod, "route_current_page", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(mod, "render_sidebar", lambda **_kwargs: None)
    monkeypatch.setattr(mod, "section", lambda *_args, **_kwargs: DummySidebar())
    called = {"sessions": 0}
    monkeypatch.setattr(
        mod,
        "instrument_cached_call",
        lambda *_args, **_kwargs: called.__setitem__(
            "sessions", called["sessions"] + 1
        ),
    )

    mod.main()

    assert called["sessions"] == 1
    assert context_calls["n"] == 1
