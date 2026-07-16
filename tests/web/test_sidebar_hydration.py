"""Tests for sidebar hydration."""

from __future__ import annotations

import pytest

from transcriptx.web.navigation import build_prerequisites
from tests.web.streamlit_doubles import DummySidebarStreamlit

_DummySidebarStreamlit = DummySidebarStreamlit
_PREREQUISITES = build_prerequisites()

_HYDRATION_PAGES = (
    "Home",
    "Library",
    "Search",
    "Settings",
    "Transcribe Audio",
    "Charts",
    "Overview",
    "Transcript",
)


def _seed_sidebar_state(page: str = "Home") -> dict[str, object]:
    return {"page": page}


def _canonical_context() -> dict[str, object]:
    return {
        "subject_type": "transcript",
        "subject_id": "slug-keep",
        "run_id": "run-keep",
    }


def _patch_sidebar_basics(monkeypatch, mod) -> None:
    monkeypatch.setattr(mod, "st", _DummySidebarStreamlit)
    import transcriptx.web.sidebar_workspace as workspace_mod

    monkeypatch.setattr(workspace_mod, "st", _DummySidebarStreamlit)


def _discovery_mocks(monkeypatch, mod) -> dict[str, int]:
    calls = {"transcripts": 0, "runs": 0, "subject": 0, "groups": 0}
    monkeypatch.setattr(
        "transcriptx.web.sidebar_options.get_transcript_dropdown_options",
        lambda: calls.__setitem__("transcripts", calls["transcripts"] + 1)
        or (["slug-1"], lambda value: value),
    )
    monkeypatch.setattr(
        mod.SubjectService,
        "resolve_current_subject",
        lambda _ss: calls.__setitem__("subject", calls["subject"] + 1),
    )
    monkeypatch.setattr(
        "transcriptx.web.cache_helpers.cached_list_runs",
        lambda *_args, **_kwargs: calls.__setitem__("runs", calls["runs"] + 1) or [],
    )
    monkeypatch.setattr(
        "transcriptx.web.cache_helpers.cached_list_groups",
        lambda: calls.__setitem__("groups", calls["groups"] + 1) or [],
    )
    return calls


@pytest.mark.parametrize("page", _HYDRATION_PAGES)
def test_sidebar_always_hydrates_workspace(monkeypatch, page: str) -> None:
    import transcriptx.web.sidebar as mod

    _DummySidebarStreamlit.session_state = _seed_sidebar_state(page)
    _DummySidebarStreamlit.button_presses = set()
    _patch_sidebar_basics(monkeypatch, mod)
    calls = _discovery_mocks(monkeypatch, mod)

    mod.render_sidebar(
        current_page=page,
        corrections_studio_available=False,
        prerequisites=_PREREQUISITES,
    )

    assert calls["transcripts"] == 1
    assert calls["subject"] >= 1


def test_charts_does_not_call_cached_list_groups_for_transcript_mode(
    monkeypatch,
) -> None:
    import transcriptx.web.sidebar as mod

    _DummySidebarStreamlit.session_state = _seed_sidebar_state("Charts")
    _DummySidebarStreamlit.button_presses = set()
    _patch_sidebar_basics(monkeypatch, mod)
    calls = _discovery_mocks(monkeypatch, mod)

    mod.render_sidebar(
        current_page="Charts",
        corrections_studio_available=False,
        prerequisites=_PREREQUISITES,
    )

    assert calls["groups"] == 0


def test_home_preserves_canonical_context(monkeypatch) -> None:
    import transcriptx.web.sidebar as mod

    _DummySidebarStreamlit.session_state = {
        **_seed_sidebar_state("Home"),
        **_canonical_context(),
    }
    _DummySidebarStreamlit.button_presses = set()
    _patch_sidebar_basics(monkeypatch, mod)
    fake_scope = type("Scope", (), {})()
    fake_subject = type(
        "ResolvedSubject",
        (),
        {
            "scope": fake_scope,
            "subject_id": "slug-keep",
            "subject_type": "transcript",
        },
    )()
    monkeypatch.setattr(
        "transcriptx.web.sidebar_options.get_transcript_dropdown_options",
        lambda: (["slug-keep"], lambda value: value),
    )
    monkeypatch.setattr(
        mod.SubjectService,
        "resolve_current_subject",
        lambda ss: fake_subject if ss.get("subject_id") == "slug-keep" else None,
    )
    monkeypatch.setattr(
        "transcriptx.web.cache_helpers.cached_list_runs",
        lambda *_args, **_kwargs: [
            type("Run", (), {"run_id": "run-keep"})(),
        ],
    )

    before = {k: _DummySidebarStreamlit.session_state[k] for k in _canonical_context()}
    mod.render_sidebar(
        current_page="Home",
        corrections_studio_available=False,
        prerequisites=_PREREQUISITES,
    )
    after = {k: _DummySidebarStreamlit.session_state[k] for k in _canonical_context()}
    assert before == after


def test_unknown_page_hydrates_workspace(monkeypatch) -> None:
    import transcriptx.web.sidebar as mod

    _DummySidebarStreamlit.session_state = _seed_sidebar_state("Not A Real Page")
    _DummySidebarStreamlit.button_presses = set()
    _patch_sidebar_basics(monkeypatch, mod)
    calls = _discovery_mocks(monkeypatch, mod)

    mod.render_sidebar(
        current_page="Not A Real Page",
        corrections_studio_available=False,
        prerequisites=_PREREQUISITES,
    )

    assert calls["transcripts"] == 1
    assert calls["subject"] >= 1


def test_home_resolves_subject_for_nav_access(monkeypatch) -> None:
    import transcriptx.web.sidebar as mod

    _DummySidebarStreamlit.session_state = _seed_sidebar_state("Home")
    _DummySidebarStreamlit.button_presses = set()
    _patch_sidebar_basics(monkeypatch, mod)
    calls = _discovery_mocks(monkeypatch, mod)

    mod.render_sidebar(
        current_page="Home",
        corrections_studio_available=False,
        prerequisites=_PREREQUISITES,
    )

    assert calls["subject"] >= 1


def test_selected_transcript_with_no_runs_shows_hint(monkeypatch) -> None:
    import transcriptx.web.sidebar as mod

    _DummySidebarStreamlit.session_state = {
        **_seed_sidebar_state("Home"),
        "subject_type": "transcript",
        "subject_type_selector": "Transcript",
        "subject_id": "slug-1",
        "subject_id_selector": "slug-1",
    }
    _DummySidebarStreamlit.button_presses = set()
    _DummySidebarStreamlit.captions = []
    _patch_sidebar_basics(monkeypatch, mod)
    fake_scope = type("Scope", (), {"scope_type": "transcript"})()
    fake_subject = type(
        "ResolvedSubject",
        (),
        {
            "scope": fake_scope,
            "subject_id": "slug-1",
            "subject_type": "transcript",
        },
    )()
    monkeypatch.setattr(
        "transcriptx.web.sidebar_options.get_transcript_dropdown_options",
        lambda: (["slug-1"], lambda value: value),
    )
    monkeypatch.setattr(
        mod.SubjectService,
        "resolve_current_subject",
        lambda ss: fake_subject if ss.get("subject_id") == "slug-1" else None,
    )
    monkeypatch.setattr(
        "transcriptx.web.cache_helpers.cached_list_runs",
        lambda *_args, **_kwargs: [],
    )

    mod.render_sidebar(
        current_page="Home",
        corrections_studio_available=False,
        prerequisites=_PREREQUISITES,
    )

    assert any(
        "No runs for this transcript yet" in caption
        for caption in _DummySidebarStreamlit.captions
    )
    assert _DummySidebarStreamlit.session_state.get("run_id") is None
