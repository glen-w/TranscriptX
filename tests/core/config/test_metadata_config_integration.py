"""Integration tests for metadata.* config resolution and validation."""

from __future__ import annotations

import pytest

from transcriptx.core.config import (
    resolve_effective_config,
    save_project_config,
    validate_config,
)
from transcriptx.core.config import persistence as config_persistence
from transcriptx.core.config.models.metadata import MetadataSettingsModel
from transcriptx.core.config.persistence import save_run_override
from transcriptx.core.utils.config import TranscriptXConfig
from transcriptx.core.utils.config.env_overrides import apply_transcriptx_env


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    cfg_dir = tmp_path / ".transcriptx"
    monkeypatch.setattr(config_persistence, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config_persistence, "CONFIG_DRAFTS_DIR", cfg_dir / "drafts")
    return cfg_dir


def test_metadata_env_duration_calculation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSCRIPTX_METADATA_DURATION_CALCULATION", "span")
    cfg = TranscriptXConfig()
    apply_transcriptx_env(cfg)
    assert cfg.metadata.duration_calculation == "span"
    monkeypatch.delenv("TRANSCRIPTX_METADATA_DURATION_CALCULATION", raising=False)


def test_metadata_env_target_on_pydantic_model() -> None:
    assert "duration_calculation" in MetadataSettingsModel.model_fields


def test_metadata_project_override_resolves(config_dir) -> None:
    save_project_config({"metadata": {"duration_calculation": "span"}})
    resolved = resolve_effective_config(run_dir=None)
    assert resolved.effective_config.metadata.duration_calculation == "span"
    assert resolved.sources_by_key.get("metadata.duration_calculation") == "project"


def test_metadata_run_override_wins(config_dir, tmp_path) -> None:
    run_dir = tmp_path / "run1"
    run_dir.mkdir()
    save_project_config({"metadata": {"duration_calculation": "max_end"}})
    save_run_override(run_dir, {"metadata": {"duration_calculation": "span"}})
    resolved = resolve_effective_config(run_dir=run_dir)
    assert resolved.effective_config.metadata.duration_calculation == "span"


def test_metadata_invalid_enum_fails_validation() -> None:
    errors = validate_config({"metadata": {"duration_calculation": "invalid"}})
    assert "metadata.duration_calculation" in errors
