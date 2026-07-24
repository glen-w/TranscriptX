"""Onboarding checklist prefs."""

from __future__ import annotations

from pathlib import Path

from transcriptx.web.onboarding.prefs import (
    REQUIRED_ITEM_IDS,
    OnboardingDraft,
    built_in_prefs,
    derived_complete,
    invalidate_onboarding_cache,
    load_onboarding_prefs,
    raw_file_revision,
    save_onboarding_prefs,
    set_item_state,
)


def test_derived_complete_requires_required_items(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "onboarding.json"
    monkeypatch.setattr(
        "transcriptx.web.onboarding.prefs.onboarding_prefs_path",
        lambda: path,
    )
    invalidate_onboarding_cache()
    prefs = built_in_prefs()
    assert derived_complete(prefs) is False
    for item_id in REQUIRED_ITEM_IDS:
        prefs.items[item_id].state = "completed"
    assert derived_complete(prefs) is True


def test_required_cannot_skip(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "onboarding.json"
    monkeypatch.setattr(
        "transcriptx.web.onboarding.prefs.onboarding_prefs_path",
        lambda: path,
    )
    invalidate_onboarding_cache()
    result = set_item_state(REQUIRED_ITEM_IDS[0], "skipped")
    assert result.ok is False


def test_corrupt_onboarding_preserves_file(tmp_path: Path) -> None:
    path = tmp_path / "onboarding.json"
    path.write_text("nope", encoding="utf-8")
    prefs, draft = load_onboarding_prefs(path)
    assert draft.recovery is True
    assert path.read_text(encoding="utf-8") == "nope"
    assert save_onboarding_prefs(draft, path=path).ok is False


def test_save_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "onboarding.json"
    prefs = built_in_prefs()
    prefs.items[REQUIRED_ITEM_IDS[0]].state = "completed"
    draft = OnboardingDraft(
        prefs=prefs,
        raw_file_revision=raw_file_revision(b""),
        path=path,
    )
    assert save_onboarding_prefs(draft, path=path).ok
    loaded, draft2 = load_onboarding_prefs(path)
    assert draft2.recovery is False
    assert loaded.items[REQUIRED_ITEM_IDS[0]].state == "completed"
