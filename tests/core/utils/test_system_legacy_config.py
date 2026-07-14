"""Tests for install-profile resolution and main TranscriptXConfig helpers.

Previously covered the deprecated ``system.TranscriptXConfig`` duplicate; that
facade was removed. Install-profile and quality-profile helpers live on
``main.TranscriptXConfig`` / ``get_install_profile``.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from transcriptx.core.utils.config import main as main_config


@pytest.mark.unit
def test_get_install_profile_returns_none_when_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "transcriptx.core.utils.paths.CONFIG_DIR",
        tmp_path,
        raising=False,
    )
    assert main_config.get_install_profile() is None


@pytest.mark.unit
def test_get_install_profile_reads_value(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "transcriptx.core.utils.paths.CONFIG_DIR",
        tmp_path,
        raising=False,
    )
    (tmp_path / "install_profile").write_text("full\n", encoding="utf-8")
    assert main_config.get_install_profile() == "full"


@pytest.mark.unit
def test_get_install_profile_empty_file_is_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "transcriptx.core.utils.paths.CONFIG_DIR",
        tmp_path,
        raising=False,
    )
    (tmp_path / "install_profile").write_text("   \n", encoding="utf-8")
    assert main_config.get_install_profile() is None


@pytest.mark.unit
def test_transcriptx_config_core_mode_false_when_install_full(
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
    cfg = main_config.TranscriptXConfig()
    assert cfg.core_mode is False


@pytest.mark.unit
def test_get_quality_filtering_config_unknown_profile_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = main_config.TranscriptXConfig()
    cfg.analysis.quality_filtering_profile = "does_not_exist"  # type: ignore[attr-defined]
    with patch("transcriptx.core.utils.logger.log_warning") as _lw:
        q = cfg.get_quality_filtering_config()
    _lw.assert_called()
    assert "weights" in q
    assert "thresholds" in q
    assert "indicators" in q


@pytest.mark.unit
def test_list_quality_profiles_returns_descriptions() -> None:
    cfg = main_config.TranscriptXConfig()
    profiles = cfg.list_quality_profiles()
    assert isinstance(profiles, dict)
    assert "balanced" in profiles
