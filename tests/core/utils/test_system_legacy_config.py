"""Tests for `transcriptx.core.utils.config.system` (legacy parallel config surface)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from transcriptx.core.utils.config import system as system_config


@pytest.mark.unit
def test_read_install_profile_returns_none_when_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "transcriptx.core.utils.paths.CONFIG_DIR",
        tmp_path,
        raising=False,
    )
    assert system_config._read_install_profile() is None


@pytest.mark.unit
def test_read_install_profile_reads_value(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "transcriptx.core.utils.paths.CONFIG_DIR",
        tmp_path,
        raising=False,
    )
    (tmp_path / "install_profile").write_text("full\n", encoding="utf-8")
    assert system_config._read_install_profile() == "full"


@pytest.mark.unit
def test_read_install_profile_empty_file_is_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "transcriptx.core.utils.paths.CONFIG_DIR",
        tmp_path,
        raising=False,
    )
    (tmp_path / "install_profile").write_text("   \n", encoding="utf-8")
    assert system_config._read_install_profile() is None


@pytest.mark.unit
def test_system_transcriptx_config_core_mode_false_when_install_full(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for key in list(os.environ):
        if key.startswith("TRANSCRIPTX_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(
        "transcriptx.core.utils.paths.CONFIG_DIR",
        tmp_path,
        raising=False,
    )
    (tmp_path / "install_profile").write_text("full", encoding="utf-8")
    cfg = system_config.TranscriptXConfig()
    assert cfg.core_mode is False


@pytest.mark.unit
def test_get_quality_filtering_config_unknown_profile_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = system_config.TranscriptXConfig()
    cfg.analysis.quality_filtering_profile = "does_not_exist"  # type: ignore[attr-defined]
    with patch("transcriptx.core.utils.logger.log_warning") as _lw:
        q = cfg.get_quality_filtering_config()
    _lw.assert_called()
    assert "weights" in q
    assert "thresholds" in q
    assert "indicators" in q


@pytest.mark.unit
def test_list_quality_profiles_returns_descriptions() -> None:
    cfg = system_config.TranscriptXConfig()
    profiles = cfg.list_quality_profiles()
    assert isinstance(profiles, dict)
    assert "balanced" in profiles


@pytest.mark.unit
def test_initialize_default_profiles_is_noop() -> None:
    assert system_config.initialize_default_profiles() is None


@pytest.mark.unit
def test_get_set_load_config_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in list(os.environ):
        if key.startswith("TRANSCRIPTX_"):
            monkeypatch.delenv(key, raising=False)
    system_config.set_config(system_config.TranscriptXConfig())
    p = tmp_path / "cfg.json"
    p.write_text('{"use_emojis": false}', encoding="utf-8")
    loaded = system_config.load_config(str(p))
    assert loaded.use_emojis is False
