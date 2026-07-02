from __future__ import annotations

import pytest

from transcriptx.web.navigation import build_prerequisites
from transcriptx.web.state import SELECTED_TRANSCRIPT_PATH
from tests.web.streamlit_doubles import DummySidebarStreamlit

_DummySidebarStreamlit = DummySidebarStreamlit
_PREREQUISITES = build_prerequisites()

_NO_HYDRATION_PAGES = (
    "Home",
    "Library",
    "Search",
    "Settings",
    "Profiles",
    "Diagnostics",
    "Statistics",
    "Transcribe Audio",
    "Import Transcript",
)

_HYDRATION_PAGES = (
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
        SELECTED_TRANSCRIPT_PATH: "/tmp/keep.json",
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
        mod.RunIndex,
        "list_runs",
        lambda *_args, **_kwargs: calls.__setitem__("runs", calls["runs"] + 1) or [],
    )
    monkeypatch.setattr(
        "transcriptx.web.cache_helpers.cached_list_groups",
        lambda: calls.__setitem__("groups", calls["groups"] + 1) or [],
    )
    return calls


@pytest.mark.parametrize("page", _NO_HYDRATION_PAGES)
def test_lightweight_pages_do_not_hydrate_workspace(monkeypatch, page: str) -> None:
    import transcriptx.web.sidebar as mod

    _DummySidebarStreamlit.session_state = _seed_sidebar_state(page)
    _DummySidebarStreamlit.button_presses = set()
    _patch_sidebar_basics(monkeypatch, mod)
    calls = _discovery_mocks(monkeypatch, mod)

    before = {**_DummySidebarStreamlit.session_state}
    mod.render_sidebar(
        current_page=page,
        corrections_studio_available=False,
        prerequisites=_PREREQUISITES,
    )

    assert calls == {"transcripts": 0, "runs": 0, "subject": 0, "groups": 0}
    for key in ("subject_type", "subject_id", "run_id", SELECTED_TRANSCRIPT_PATH):
        assert _DummySidebarStreamlit.session_state.get(key) == before.get(key)


@pytest.mark.parametrize("page", _HYDRATION_PAGES)
def test_context_pages_hydrate_workspace(monkeypatch, page: str) -> None:
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
    _discovery_mocks(monkeypatch, mod)

    before = {k: _DummySidebarStreamlit.session_state[k] for k in _canonical_context()}
    mod.render_sidebar(
        current_page="Home",
        corrections_studio_available=False,
        prerequisites=_PREREQUISITES,
    )
    after = {k: _DummySidebarStreamlit.session_state[k] for k in _canonical_context()}
    assert before == after


def test_unknown_page_does_not_hydrate_workspace(monkeypatch) -> None:
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

    assert calls == {"transcripts": 0, "runs": 0, "subject": 0, "groups": 0}


def test_home_does_not_resolve_subject_for_nav_access(monkeypatch) -> None:
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

    assert calls["subject"] == 0
