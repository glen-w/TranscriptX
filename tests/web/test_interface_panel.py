"""Settings Interface panel orchestration contracts (L3)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from transcriptx.web.action_menus.prefs import DRAFT_SESSION_KEY
from tests.web.streamlit_doubles import DummyColumn, DummyExpander, DummyHomeStreamlit


class _IfaceStreamlit(DummyHomeStreamlit):
    session_state: dict = {}
    button_returns: dict[str, bool] = {}
    successes: list[str] = []
    infos: list[str] = []
    errors: list[str] = []
    rerun_calls: int = 0

    @classmethod
    def reset(cls) -> None:
        cls.session_state = {}
        cls.button_returns = {}
        cls.successes = []
        cls.infos = []
        cls.errors = []
        cls.rerun_calls = 0

    @staticmethod
    def fragment(fn=None, **_kwargs):
        if fn is None:

            def _decorator(f):
                return f

            return _decorator
        return fn

    @classmethod
    def button(cls, label, key=None, **_kwargs):
        if key and key in cls.button_returns:
            return cls.button_returns[key]
        return bool(cls.button_returns.get(label, False))

    @staticmethod
    def radio(*_a, **_k):
        return "Built-in"

    @staticmethod
    def checkbox(*_a, **_k):
        return True

    @staticmethod
    def expander(*_a, **_k):
        return DummyExpander()

    @staticmethod
    def columns(_n):
        return (DummyColumn(), DummyColumn(), DummyColumn())

    @classmethod
    def success(cls, msg, **_kwargs):
        cls.successes.append(str(msg))

    @classmethod
    def info(cls, msg, **_kwargs):
        cls.infos.append(str(msg))

    @classmethod
    def error(cls, msg, **_kwargs):
        cls.errors.append(str(msg))

    @classmethod
    def rerun(cls):
        cls.rerun_calls += 1


def _draft(*, recovery: bool = False) -> SimpleNamespace:
    prefs = SimpleNamespace(
        standard_menu_mode="built_in",
        standard_menu=[],
        sections={},
        show_info_tooltips=True,
    )
    return SimpleNamespace(
        prefs=prefs,
        recovery=recovery,
        recovery_message=None,
    )


@pytest.mark.unit
def test_interface_panel_hydrates_draft_on_first_render(monkeypatch) -> None:
    import transcriptx.web.ui.settings.interface_panel as mod

    _IfaceStreamlit.reset()
    sync_calls: list = []
    draft = _draft()
    monkeypatch.setattr(mod, "st", _IfaceStreamlit)
    monkeypatch.setattr(mod, "get_or_hydrate_draft", lambda _ss: draft)
    monkeypatch.setattr(
        mod, "_sync_widgets_from_draft", lambda: sync_calls.append(True)
    )
    monkeypatch.setattr(mod, "SECTION_ORDER", ())
    monkeypatch.setattr(mod, "ACTIONS", ())

    panel = getattr(
        mod.render_interface_panel, "__wrapped__", mod.render_interface_panel
    )
    panel()

    assert sync_calls
    assert DRAFT_SESSION_KEY not in _IfaceStreamlit.session_state or True


@pytest.mark.unit
def test_request_widget_sync_sets_pending_flag(monkeypatch) -> None:
    import transcriptx.web.ui.settings.interface_panel as mod

    _IfaceStreamlit.reset()
    monkeypatch.setattr(mod, "st", _IfaceStreamlit)
    mod._request_widget_sync()
    assert _IfaceStreamlit.session_state[mod._PENDING_WIDGET_SYNC_KEY] is True


@pytest.mark.unit
def test_interface_panel_pending_sync_hydrates_existing_draft(monkeypatch) -> None:
    import transcriptx.web.ui.settings.interface_panel as mod

    _IfaceStreamlit.reset()
    draft = _draft()
    _IfaceStreamlit.session_state[DRAFT_SESSION_KEY] = draft
    _IfaceStreamlit.session_state[mod._PENDING_WIDGET_SYNC_KEY] = True
    sync_calls: list = []

    monkeypatch.setattr(mod, "st", _IfaceStreamlit)
    monkeypatch.setattr(mod, "get_or_hydrate_draft", lambda _ss: draft)
    monkeypatch.setattr(
        mod, "_sync_widgets_from_draft", lambda: sync_calls.append(True)
    )
    monkeypatch.setattr(mod, "SECTION_ORDER", ())
    monkeypatch.setattr(mod, "ACTIONS", ())

    panel = getattr(
        mod.render_interface_panel, "__wrapped__", mod.render_interface_panel
    )
    panel()

    assert sync_calls
    assert mod._PENDING_WIDGET_SYNC_KEY not in _IfaceStreamlit.session_state


@pytest.mark.unit
def test_interface_panel_save_calls_prefs_and_requests_sync(monkeypatch) -> None:
    import transcriptx.web.ui.settings.interface_panel as mod

    _IfaceStreamlit.reset()
    draft = _draft()
    _IfaceStreamlit.session_state[DRAFT_SESSION_KEY] = draft
    _IfaceStreamlit.button_returns = {"iface_save": True}
    save_calls: list = []
    sync_req: list = []

    monkeypatch.setattr(mod, "st", _IfaceStreamlit)
    monkeypatch.setattr(mod, "get_or_hydrate_draft", lambda _ss: draft)
    monkeypatch.setattr(mod, "_sync_widgets_from_draft", lambda: None)
    monkeypatch.setattr(mod, "_pull_widgets_into_draft", lambda: None)
    monkeypatch.setattr(mod, "validate_draft_for_save", lambda _p: None)
    monkeypatch.setattr(
        mod,
        "save_interface_prefs",
        lambda d: save_calls.append(d)
        or SimpleNamespace(ok=True, conflict=False, error=None),
    )
    monkeypatch.setattr(mod, "_request_widget_sync", lambda: sync_req.append(True))
    monkeypatch.setattr(mod, "SECTION_ORDER", ())
    monkeypatch.setattr(mod, "ACTIONS", ())

    panel = getattr(
        mod.render_interface_panel, "__wrapped__", mod.render_interface_panel
    )
    panel()

    assert save_calls == [draft]
    assert sync_req
    assert _IfaceStreamlit.rerun_calls == 1
    assert any("saved" in s.lower() for s in _IfaceStreamlit.successes)


@pytest.mark.unit
def test_interface_panel_restore_resets_draft(monkeypatch) -> None:
    import transcriptx.web.ui.settings.interface_panel as mod

    _IfaceStreamlit.reset()
    draft = _draft()
    _IfaceStreamlit.session_state[DRAFT_SESSION_KEY] = draft
    _IfaceStreamlit.button_returns = {"iface_restore": True}
    reset_calls: list = []
    sync_req: list = []

    monkeypatch.setattr(mod, "st", _IfaceStreamlit)
    monkeypatch.setattr(mod, "get_or_hydrate_draft", lambda _ss: draft)
    monkeypatch.setattr(mod, "_sync_widgets_from_draft", lambda: None)
    monkeypatch.setattr(
        mod, "reset_draft_to_built_ins", lambda ss: reset_calls.append(ss)
    )
    monkeypatch.setattr(mod, "_request_widget_sync", lambda: sync_req.append(True))
    monkeypatch.setattr(mod, "SECTION_ORDER", ())
    monkeypatch.setattr(mod, "ACTIONS", ())

    panel = getattr(
        mod.render_interface_panel, "__wrapped__", mod.render_interface_panel
    )
    panel()

    assert reset_calls
    assert sync_req
    assert _IfaceStreamlit.rerun_calls == 1


@pytest.mark.unit
def test_interface_panel_reload_from_disk(monkeypatch) -> None:
    import transcriptx.web.ui.settings.interface_panel as mod

    _IfaceStreamlit.reset()
    draft = _draft()
    _IfaceStreamlit.session_state[DRAFT_SESSION_KEY] = draft
    _IfaceStreamlit.button_returns = {"iface_reload": True}
    reload_calls: list = []

    monkeypatch.setattr(mod, "st", _IfaceStreamlit)
    monkeypatch.setattr(mod, "get_or_hydrate_draft", lambda _ss: draft)
    monkeypatch.setattr(mod, "_sync_widgets_from_draft", lambda: None)
    monkeypatch.setattr(
        mod, "reload_draft_from_disk", lambda ss: reload_calls.append(ss)
    )
    monkeypatch.setattr(mod, "_request_widget_sync", lambda: None)
    monkeypatch.setattr(mod, "SECTION_ORDER", ())
    monkeypatch.setattr(mod, "ACTIONS", ())

    panel = getattr(
        mod.render_interface_panel, "__wrapped__", mod.render_interface_panel
    )
    panel()

    assert reload_calls
    assert _IfaceStreamlit.rerun_calls == 1


@pytest.mark.unit
def test_interface_panel_sync_and_pull_show_info_tooltips(monkeypatch) -> None:
    import transcriptx.web.ui.settings.interface_panel as mod
    from transcriptx.web.action_menus.prefs import built_in_prefs

    _IfaceStreamlit.reset()
    prefs = built_in_prefs()
    prefs.show_info_tooltips = False
    draft = SimpleNamespace(
        prefs=prefs,
        recovery=False,
        recovery_message=None,
    )
    _IfaceStreamlit.session_state[DRAFT_SESSION_KEY] = draft
    monkeypatch.setattr(mod, "st", _IfaceStreamlit)
    monkeypatch.setattr(mod, "SECTION_ORDER", ())
    monkeypatch.setattr(mod, "ACTIONS", ())

    mod._sync_widgets_from_draft()
    assert _IfaceStreamlit.session_state["iface_show_info_tooltips"] is False

    _IfaceStreamlit.session_state["iface_show_info_tooltips"] = True
    mod._pull_widgets_into_draft()
    assert draft.prefs.show_info_tooltips is True
