"""Presentation-mode prefs, seed, and visibility."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.web.navigation import get_page_spec
from transcriptx.web.presentation.prefs import (
    MODE_FULL,
    MODE_GUIDED,
    PresentationDraft,
    built_in_prefs,
    invalidate_presentation_cache,
    load_presentation_prefs,
    prefs_integrity_hash,
    raw_file_revision,
    save_presentation_prefs,
)
from transcriptx.web.presentation.resolve import set_presentation_mode
from transcriptx.web.presentation.seed import (
    seed_presentation_mode_if_needed,
    workspace_looks_existing,
)
from transcriptx.web.presentation.visibility import (
    page_visible_in_presentation,
    visible_pages_in_section,
)


@pytest.fixture(autouse=True)
def _clear_presentation_cache():
    invalidate_presentation_cache()
    yield
    invalidate_presentation_cache()


def test_corrupt_prefs_recovery_preserves_file(tmp_path: Path) -> None:
    path = tmp_path / "presentation_mode.json"
    path.write_text("{not-json", encoding="utf-8")
    prefs, draft = load_presentation_prefs(path)
    assert prefs.mode == MODE_GUIDED
    assert draft.recovery is True
    assert path.read_text(encoding="utf-8") == "{not-json"
    result = save_presentation_prefs(draft, path=path)
    assert result.ok is False
    assert path.read_text(encoding="utf-8") == "{not-json"


def test_hash_mismatch_recovery(tmp_path: Path) -> None:
    import json

    prefs_dict = {"mode": MODE_FULL}
    envelope = {
        "schema_version": 1,
        "prefs": prefs_dict,
        "prefs_hash": "deadbeef",
    }
    path = tmp_path / "presentation_mode.json"
    path.write_text(json.dumps(envelope), encoding="utf-8")
    prefs, draft = load_presentation_prefs(path)
    assert draft.recovery is True
    assert prefs.mode == MODE_GUIDED


def test_cas_conflict(tmp_path: Path) -> None:
    path = tmp_path / "presentation_mode.json"
    prefs = built_in_prefs(mode=MODE_GUIDED)
    draft = PresentationDraft(
        prefs=prefs,
        raw_file_revision=raw_file_revision(b""),
        path=path,
    )
    assert save_presentation_prefs(draft, path=path).ok
    # Stale revision
    stale = PresentationDraft(
        prefs=built_in_prefs(mode=MODE_FULL),
        raw_file_revision=raw_file_revision(b""),
        path=path,
    )
    result = save_presentation_prefs(stale, path=path)
    assert result.ok is False
    assert result.conflict is True


def test_seed_empty_workspace_guided(tmp_path: Path) -> None:
    cfg = tmp_path / "cfg"
    out = tmp_path / "out"
    cfg.mkdir()
    out.mkdir()
    path = cfg / "presentation_mode.json"
    mode = seed_presentation_mode_if_needed(
        path, config_dir=cfg, outputs_dir=out
    )
    assert mode == MODE_GUIDED
    assert path.exists()
    # Honour existing
    assert (
        seed_presentation_mode_if_needed(path, config_dir=cfg, outputs_dir=out)
        == MODE_GUIDED
    )


def test_seed_existing_workspace_full(tmp_path: Path) -> None:
    cfg = tmp_path / "cfg"
    out = tmp_path / "out"
    cfg.mkdir()
    out.mkdir()
    (cfg / "config.json").write_text("{}", encoding="utf-8")
    assert workspace_looks_existing(config_dir=cfg, outputs_dir=out)
    path = cfg / "presentation_mode.json"
    mode = seed_presentation_mode_if_needed(
        path, config_dir=cfg, outputs_dir=out
    )
    assert mode == MODE_FULL


def test_visibility_filters_full_only() -> None:
    prep = get_page_spec("Audio Prep")
    home = get_page_spec("Home")
    assert page_visible_in_presentation(prep, MODE_GUIDED) is False
    assert page_visible_in_presentation(prep, MODE_FULL) is True
    assert page_visible_in_presentation(home, MODE_GUIDED) is True
    tools = visible_pages_in_section("tools", MODE_GUIDED)
    assert all(p.key != "Audio Prep" for p in tools)


def test_set_presentation_mode_roundtrip(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "presentation_mode.json"
    prefs = built_in_prefs(mode=MODE_GUIDED)
    draft = PresentationDraft(
        prefs=prefs,
        raw_file_revision=raw_file_revision(b""),
        path=path,
    )
    assert save_presentation_prefs(draft, path=path).ok
    monkeypatch.setattr(
        "transcriptx.web.presentation.resolve.load_presentation_prefs",
        lambda p=None: load_presentation_prefs(path),
    )
    monkeypatch.setattr(
        "transcriptx.web.presentation.resolve.save_presentation_prefs",
        lambda d, path=None: save_presentation_prefs(d, path=path),
    )
    result = set_presentation_mode(MODE_FULL)
    assert result.ok
    loaded, _ = load_presentation_prefs(path)
    assert loaded.mode == MODE_FULL


def test_integrity_hash_stable() -> None:
    a = prefs_integrity_hash({"mode": MODE_GUIDED})
    b = prefs_integrity_hash({"mode": MODE_GUIDED})
    assert a == b
    assert a != prefs_integrity_hash({"mode": MODE_FULL})
