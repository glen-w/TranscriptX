from __future__ import annotations


from transcriptx.web.state import PAGE_KEY, TX_NAV_EXPANDER_VIEW


class _DummySidebar:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _DummyStreamlit:
    def __init__(self) -> None:
        self.session_state: dict[str, object] = {}
        self.query_params: dict[str, str] = {}
        self.sidebar = _DummySidebar()

    @staticmethod
    def error(*_args, **_kwargs):
        return None

    @staticmethod
    def exception(*_args, **_kwargs):
        return None

    @staticmethod
    def rerun():
        return None


def test_home_cold_render_skips_session_discovery(monkeypatch) -> None:
    import transcriptx.web.app as mod

    dummy_st = _DummyStreamlit()
    monkeypatch.setattr(mod, "st", dummy_st)
    monkeypatch.setattr(mod, "start_run", lambda **_kwargs: "run-1")
    monkeypatch.setattr(mod, "record_elapsed_section", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(mod, "finish_run", lambda **_kwargs: None)
    monkeypatch.setattr(mod, "consume_page_flash", lambda: None)
    monkeypatch.setattr(mod, "render_context_bar", lambda _ss: None)
    monkeypatch.setattr(mod, "route_current_page", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(mod, "render_sidebar", lambda **_kwargs: None)
    monkeypatch.setattr(mod, "section", lambda *_args, **_kwargs: _DummySidebar())
    monkeypatch.setattr(
        mod, "should_hydrate_workspace_context", lambda *_args, **_kwargs: False
    )
    called = {"sessions": 0}
    monkeypatch.setattr(
        mod,
        "instrument_cached_call",
        lambda *_args, **_kwargs: called.__setitem__(
            "sessions", called["sessions"] + 1
        ),
    )
    monkeypatch.setattr(
        mod, "normalize_navigation_context_from_session", lambda _ss: None
    )

    mod.main()

    assert called["sessions"] == 0


def test_home_open_view_triggers_session_discovery(monkeypatch) -> None:
    import transcriptx.web.app as mod

    dummy_st = _DummyStreamlit()
    dummy_st.session_state = {PAGE_KEY: "Home", TX_NAV_EXPANDER_VIEW: True}
    monkeypatch.setattr(mod, "st", dummy_st)
    monkeypatch.setattr(mod, "start_run", lambda **_kwargs: "run-1")
    monkeypatch.setattr(mod, "record_elapsed_section", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(mod, "finish_run", lambda **_kwargs: None)
    monkeypatch.setattr(mod, "consume_page_flash", lambda: None)
    monkeypatch.setattr(mod, "render_context_bar", lambda _ss: None)
    monkeypatch.setattr(mod, "route_current_page", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(mod, "render_sidebar", lambda **_kwargs: None)
    monkeypatch.setattr(mod, "section", lambda *_args, **_kwargs: _DummySidebar())
    called = {"sessions": 0}
    monkeypatch.setattr(
        mod,
        "instrument_cached_call",
        lambda *_args, **_kwargs: called.__setitem__(
            "sessions", called["sessions"] + 1
        ),
    )
    monkeypatch.setattr(
        mod, "normalize_navigation_context_from_session", lambda _ss: None
    )

    mod.main()

    assert called["sessions"] == 1
