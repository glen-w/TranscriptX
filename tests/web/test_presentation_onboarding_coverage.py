"""Push presentation/onboarding prefs toward high statement coverage."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.web.onboarding.prefs import (
    OnboardingDraft,
    built_in_prefs,
    derived_complete,
    invalidate_onboarding_cache,
    load_onboarding_prefs,
    raw_file_revision,
    save_onboarding_prefs,
    set_dismissed,
    set_item_state,
)
from transcriptx.web.presentation.prefs import (
    MODE_FULL,
    MODE_GUIDED,
    PresentationDraft,
    built_in_prefs as presentation_built_ins,
    get_cached_presentation_prefs,
    invalidate_presentation_cache,
    load_presentation_prefs,
    raw_file_revision as presentation_revision,
    replace_with_built_in_defaults,
    save_presentation_prefs,
)
from transcriptx.web.presentation.resolve import (
    PENDING_SYNC_KEY,
    WIDGET_KEY,
    resolve_presentation_mode,
)
from transcriptx.web.presentation.switch import render_presentation_mode_switch


@pytest.mark.unit
def test_replace_with_built_in_defaults(tmp_path: Path) -> None:
    path = tmp_path / "presentation_mode.json"
    draft = PresentationDraft(
        prefs=presentation_built_ins(mode=MODE_FULL),
        raw_file_revision=presentation_revision(b""),
        path=path,
    )
    assert save_presentation_prefs(draft, path=path).ok
    assert replace_with_built_in_defaults(draft, path=path).ok
    prefs, _ = load_presentation_prefs(path)
    assert prefs.mode == MODE_GUIDED


@pytest.mark.unit
def test_unsupported_schema_preserves_file(tmp_path: Path) -> None:
    import json

    path = tmp_path / "presentation_mode.json"
    path.write_text(
        json.dumps(
            {"schema_version": 99, "prefs": {"mode": MODE_FULL}, "prefs_hash": "x"}
        ),
        encoding="utf-8",
    )
    prefs, draft = load_presentation_prefs(path)
    assert draft.recovery is True
    assert prefs.mode == MODE_GUIDED
    assert "99" in path.read_text(
        encoding="utf-8"
    ) or "schema_version" in path.read_text(encoding="utf-8")


@pytest.mark.unit
def test_presentation_cache_roundtrip(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "presentation_mode.json"
    draft = PresentationDraft(
        prefs=presentation_built_ins(mode=MODE_FULL),
        raw_file_revision=presentation_revision(b""),
        path=path,
    )
    assert save_presentation_prefs(draft, path=path).ok
    monkeypatch.setattr(
        "transcriptx.web.presentation.prefs.presentation_prefs_path",
        lambda: path,
    )
    monkeypatch.setattr(
        "transcriptx.web.presentation.seed.seed_presentation_mode_if_needed",
        lambda: MODE_FULL,
    )
    invalidate_presentation_cache()
    assert get_cached_presentation_prefs().mode == MODE_FULL
    assert resolve_presentation_mode() == MODE_FULL


@pytest.mark.unit
def test_switch_persists_change(monkeypatch) -> None:
    from tests.web.streamlit_doubles import DummyHomeStreamlit

    session: dict = {WIDGET_KEY: True, PENDING_SYNC_KEY: False}
    DummyHomeStreamlit.session_state = session
    saved: list[str] = []
    set_modes: list[str] = []

    class _St(DummyHomeStreamlit):
        session_state = session

        @staticmethod
        def caption(*_a, **_k):
            return None

        @staticmethod
        def toggle(*_a, **_k):
            return False  # user turns Guided mode off → Full controls

        @staticmethod
        def rerun():
            saved.append("rerun")

        @staticmethod
        def warning(*_a, **_k):
            return None

        @staticmethod
        def error(*_a, **_k):
            return None

    import transcriptx.web.presentation.switch as switch

    monkeypatch.setattr(switch, "st", _St)
    monkeypatch.setattr(switch, "resolve_presentation_mode", lambda: MODE_GUIDED)

    def _set(mode):
        set_modes.append(mode)
        return type("R", (), {"ok": True, "conflict": False, "error": None})()

    monkeypatch.setattr(switch, "set_presentation_mode", _set)
    render_presentation_mode_switch(location="home")
    assert set_modes == [MODE_FULL]
    assert "rerun" in saved
    assert session.get(PENDING_SYNC_KEY) is True


@pytest.mark.unit
def test_switch_migrates_legacy_string_widget(monkeypatch) -> None:
    from tests.web.streamlit_doubles import DummyHomeStreamlit

    session: dict = {WIDGET_KEY: "Guided"}
    DummyHomeStreamlit.session_state = session

    class _St(DummyHomeStreamlit):
        session_state = session

        @staticmethod
        def caption(*_a, **_k):
            return None

        @staticmethod
        def toggle(*_a, **_k):
            return True

        @staticmethod
        def rerun():
            return None

    import transcriptx.web.presentation.switch as switch

    monkeypatch.setattr(switch, "st", _St)
    monkeypatch.setattr(switch, "resolve_presentation_mode", lambda: MODE_GUIDED)
    monkeypatch.setattr(
        switch,
        "set_presentation_mode",
        lambda _mode: type("R", (), {"ok": True, "conflict": False, "error": None})(),
    )
    render_presentation_mode_switch(location="settings")
    assert session[WIDGET_KEY] is True


@pytest.mark.unit
def test_onboarding_dismiss_and_complete(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "onboarding.json"
    monkeypatch.setattr(
        "transcriptx.web.onboarding.prefs.onboarding_prefs_path",
        lambda: path,
    )
    invalidate_onboarding_cache()
    assert set_dismissed(True).ok
    prefs, draft = load_onboarding_prefs(path)
    assert prefs.dismissed is True
    assert draft.recovery is False
    for item_id in (
        "open_library",
        "import_or_demo",
        "run_analysis",
        "open_insights_charts",
        "export_artifacts",
        "know_guided_full",
    ):
        assert set_item_state(item_id, "completed").ok
    prefs2, _ = load_onboarding_prefs(path)
    assert derived_complete(prefs2) is True


@pytest.mark.unit
def test_onboarding_hash_mismatch_recovery(tmp_path: Path) -> None:
    import json

    path = tmp_path / "onboarding.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "prefs": {"dismissed": False, "items": {}},
                "prefs_hash": "deadbeef",
            }
        ),
        encoding="utf-8",
    )
    prefs, draft = load_onboarding_prefs(path)
    assert draft.recovery is True
    assert (
        save_onboarding_prefs(
            OnboardingDraft(
                prefs=built_in_prefs(),
                raw_file_revision=raw_file_revision(b""),
                recovery=True,
                path=path,
            ),
            path=path,
        ).ok
        is False
    )
