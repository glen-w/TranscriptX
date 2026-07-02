from __future__ import annotations

from transcriptx.web.sidebar_state import apply_transitional_sidebar_backfill
from transcriptx.web.state import (
    SELECTED_TRANSCRIPT_PATH,
    TX_NAV_EXPANDER_CONFIG,
    TX_NAV_EXPANDER_TOOLS,
    TX_NAV_EXPANDER_VIEW,
    TX_NAV_EXPANDER_WORKFLOW,
    TX_NAV_WORKSPACE_SELECTOR_REQUESTED,
)


class _DummySidebarStreamlit:
    session_state: dict[str, object] = {}
    captions: list[str] = []
    button_presses: set[str] = set()
    toggle_calls: list[tuple[str, str | None, bool]] = []

    @staticmethod
    def markdown(*_args, **_kwargs):
        return None

    @classmethod
    def button(cls, _label, key=None, **_kwargs):
        return bool(key and key in cls.button_presses)

    @staticmethod
    def rerun():
        return None

    @staticmethod
    def radio(_label, options, index=0, **_kwargs):
        return options[index]

    @staticmethod
    def selectbox(_label, options, index=0, **_kwargs):
        return options[index]

    @classmethod
    def caption(cls, text, **_kwargs):
        cls.captions.append(text)
        return None

    @classmethod
    def toggle(cls, label, *, value=False, key=None, **_kwargs):
        cls.toggle_calls.append((label, key, value))
        if key is not None and key in cls.session_state:
            return bool(cls.session_state[key])
        return value


def _seed_sidebar_state() -> dict[str, object]:
    return {
        "page": "Home",
        TX_NAV_EXPANDER_WORKFLOW: False,
        TX_NAV_EXPANDER_VIEW: False,
        TX_NAV_EXPANDER_TOOLS: False,
        TX_NAV_EXPANDER_CONFIG: False,
        "tx_nav_sidebar_seeded": True,
        "tx_nav_prev_should_prioritize_view": False,
    }


def _canonical_context() -> dict[str, object]:
    return {
        "subject_type": "transcript",
        "subject_id": "slug-keep",
        "run_id": "run-keep",
        SELECTED_TRANSCRIPT_PATH: "/tmp/keep.json",
    }


def _patch_sidebar_basics(monkeypatch, mod) -> None:
    monkeypatch.setattr(mod, "st", _DummySidebarStreamlit)
    monkeypatch.setattr(mod, "context_readiness", lambda _ss: {})
    monkeypatch.setattr(
        mod,
        "evaluate_page_access",
        lambda *_args, **_kwargs: type(
            "A", (), {"allowed": False, "help_text": None}
        )(),
    )
    monkeypatch.setattr(
        mod,
        "derive_sidebar_state",
        lambda _ss: type("S", (), {"prioritize_view": False})(),
    )


def test_collapsed_view_does_not_hydrate_workspace(monkeypatch) -> None:
    import transcriptx.web.sidebar as mod

    _DummySidebarStreamlit.session_state = _seed_sidebar_state()
    _DummySidebarStreamlit.captions = []
    _DummySidebarStreamlit.button_presses = set()
    _DummySidebarStreamlit.toggle_calls = []
    _patch_sidebar_basics(monkeypatch, mod)
    monkeypatch.setattr(
        mod, "apply_transitional_sidebar_backfill", lambda *_args, **_kwargs: None
    )
    calls = {"transcripts": 0, "runs": 0, "subject": 0, "groups": 0}
    monkeypatch.setattr(
        mod,
        "get_transcript_dropdown_options",
        lambda: calls.__setitem__("transcripts", calls["transcripts"] + 1)
        or ([], lambda x: x),
    )
    monkeypatch.setattr(
        mod.SubjectService,
        "resolve_current_subject",
        lambda _ss: calls.__setitem__("subject", calls["subject"] + 1),
    )
    monkeypatch.setattr(
        mod.RunIndex,
        "list_runs",
        lambda *_args, **_kwargs: calls.__setitem__("runs", calls["runs"] + 1) or [],
    )
    monkeypatch.setattr(
        "transcriptx.web.cache_helpers.cached_list_groups",
        lambda: calls.__setitem__("groups", calls["groups"] + 1) or [],
    )

    before = {**_DummySidebarStreamlit.session_state}
    mod.render_sidebar(
        current_page="Home",
        corrections_studio_available=False,
        prerequisites={},
    )

    assert calls == {"transcripts": 0, "runs": 0, "subject": 0, "groups": 0}
    assert (
        "Open View to load transcript and run selectors"
        in _DummySidebarStreamlit.captions
    )
    for key in ("subject_type", "subject_id", "run_id", SELECTED_TRANSCRIPT_PATH):
        assert _DummySidebarStreamlit.session_state.get(key) == before.get(key)


def test_open_view_hydrates_workspace_on_home(monkeypatch) -> None:
    import transcriptx.web.sidebar as mod

    _DummySidebarStreamlit.session_state = {
        **_seed_sidebar_state(),
        TX_NAV_EXPANDER_VIEW: True,
    }
    _DummySidebarStreamlit.captions = []
    _DummySidebarStreamlit.button_presses = set()
    _DummySidebarStreamlit.toggle_calls = []
    _patch_sidebar_basics(monkeypatch, mod)
    monkeypatch.setattr(
        mod, "apply_transitional_sidebar_backfill", lambda *_args, **_kwargs: None
    )
    calls = {"transcripts": 0}
    monkeypatch.setattr(
        mod,
        "get_transcript_dropdown_options",
        lambda: calls.__setitem__("transcripts", calls["transcripts"] + 1)
        or (["slug-1"], lambda value: value),
    )
    monkeypatch.setattr(mod.SubjectService, "resolve_current_subject", lambda _ss: None)
    monkeypatch.setattr(mod.RunIndex, "list_runs", lambda *_args, **_kwargs: [])

    mod.render_sidebar(
        current_page="Home",
        corrections_studio_available=False,
        prerequisites={},
    )

    assert calls["transcripts"] == 1


def test_run_scoped_page_hydrates_workspace(monkeypatch) -> None:
    import transcriptx.web.sidebar as mod

    _DummySidebarStreamlit.session_state = _seed_sidebar_state()
    _DummySidebarStreamlit.captions = []
    _DummySidebarStreamlit.button_presses = set()
    _DummySidebarStreamlit.toggle_calls = []
    _patch_sidebar_basics(monkeypatch, mod)
    monkeypatch.setattr(
        mod, "apply_transitional_sidebar_backfill", lambda *_args, **_kwargs: None
    )
    calls = {"transcripts": 0}
    monkeypatch.setattr(
        mod,
        "get_transcript_dropdown_options",
        lambda: calls.__setitem__("transcripts", calls["transcripts"] + 1)
        or (["slug-1"], lambda value: value),
    )
    monkeypatch.setattr(mod.SubjectService, "resolve_current_subject", lambda _ss: None)
    monkeypatch.setattr(mod.RunIndex, "list_runs", lambda *_args, **_kwargs: [])

    mod.render_sidebar(
        current_page="Charts",
        corrections_studio_available=False,
        prerequisites={},
    )

    assert calls["transcripts"] == 1


def test_collapsed_view_does_not_mutate_canonical_context(monkeypatch) -> None:
    import transcriptx.web.sidebar as mod

    _DummySidebarStreamlit.session_state = {
        **_seed_sidebar_state(),
        **_canonical_context(),
    }
    _DummySidebarStreamlit.captions = []
    _DummySidebarStreamlit.button_presses = set()
    _DummySidebarStreamlit.toggle_calls = []
    _patch_sidebar_basics(monkeypatch, mod)
    monkeypatch.setattr(
        mod,
        "get_transcript_dropdown_options",
        lambda: (["slug-1"], lambda value: value),
    )
    monkeypatch.setattr(mod.SubjectService, "resolve_current_subject", lambda _ss: None)
    monkeypatch.setattr(mod.RunIndex, "list_runs", lambda *_args, **_kwargs: [])

    before = {k: _DummySidebarStreamlit.session_state[k] for k in _canonical_context()}
    apply_transitional_sidebar_backfill(
        _DummySidebarStreamlit.session_state,
        prioritize_view=False,
    )
    mod.render_sidebar(
        current_page="Home",
        corrections_studio_available=False,
        prerequisites={},
    )
    after = {k: _DummySidebarStreamlit.session_state[k] for k in _canonical_context()}
    assert before == after


def test_sidebar_explicit_load_still_works_when_view_collapsed(monkeypatch) -> None:
    import transcriptx.web.sidebar as mod

    _DummySidebarStreamlit.session_state = {
        **_seed_sidebar_state(),
        TX_NAV_WORKSPACE_SELECTOR_REQUESTED: True,
    }
    _DummySidebarStreamlit.captions = []
    _DummySidebarStreamlit.button_presses = set()
    _DummySidebarStreamlit.toggle_calls = []
    _patch_sidebar_basics(monkeypatch, mod)
    monkeypatch.setattr(
        mod, "apply_transitional_sidebar_backfill", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        mod,
        "get_transcript_dropdown_options",
        lambda: (["slug-1"], lambda value: value),
    )
    monkeypatch.setattr(mod.SubjectService, "resolve_current_subject", lambda _ss: None)
    monkeypatch.setattr(mod.RunIndex, "list_runs", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        _DummySidebarStreamlit,
        "selectbox",
        lambda _label, options, index=0, **_kwargs: options[1],
    )

    mod.render_sidebar(
        current_page="Home",
        corrections_studio_available=False,
        prerequisites={},
    )

    assert _DummySidebarStreamlit.session_state["subject_id"] == "slug-1"


def test_sidebar_explicit_load_populates_transcript_selector(monkeypatch) -> None:
    test_sidebar_explicit_load_still_works_when_view_collapsed(monkeypatch)
