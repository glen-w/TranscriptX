"""Metadata section visibility in to_dict, registry, and file loading."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from transcriptx.core.config import resolve_effective_config, save_project_config
from transcriptx.core.config.registry import build_registry
from transcriptx.core.config import persistence as config_persistence
from transcriptx.core.utils.config import TranscriptXConfig


def test_to_dict_includes_metadata_fields() -> None:
    cfg = TranscriptXConfig()
    payload = cfg.to_dict()
    meta = payload["metadata"]
    assert meta["duration_calculation"] == "max_end"
    assert meta["listing_word_count_fallback"] == "in_memory"
    assert meta["auto_refresh_on_write"] is True
    assert meta["legacy_words_alias"] is True


def test_build_registry_includes_metadata_keys() -> None:
    reg = build_registry()
    for key, default in (
        ("metadata.duration_calculation", "max_end"),
        ("metadata.listing_word_count_fallback", "in_memory"),
        ("metadata.auto_refresh_on_write", True),
        ("metadata.legacy_words_alias", True),
    ):
        assert key in reg, key
        assert reg[key].default == default


def test_project_config_metadata_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config_persistence, "CONFIG_DIR", tmp_path / ".transcriptx")
    monkeypatch.setattr(
        config_persistence,
        "CONFIG_DRAFTS_DIR",
        config_persistence.CONFIG_DIR / "drafts",
    )
    save_project_config({"metadata": {"duration_calculation": "span"}})
    resolved = resolve_effective_config(run_dir=None)
    assert resolved.effective_config.metadata.duration_calculation == "span"


def test_load_from_file_applies_metadata_section() -> None:
    cfg = TranscriptXConfig()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as handle:
        json.dump(
            {"metadata": {"listing_word_count_fallback": "metadata_only"}},
            handle,
        )
        path = handle.name
    try:
        cfg._load_from_file(path)
    finally:
        Path(path).unlink(missing_ok=True)
    assert cfg.metadata.listing_word_count_fallback == "metadata_only"
