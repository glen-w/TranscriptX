"""Integration tests for analysis.acts config resolution and validation."""

from __future__ import annotations

import pytest

from transcriptx.core.config import (
    resolve_effective_config,
    save_project_config,
    validate_config,
)
from transcriptx.core.config import persistence as config_persistence
from transcriptx.core.config.models.acts import ActsSettingsModel
from transcriptx.core.utils.config import TranscriptXConfig
from transcriptx.core.utils.config.env_overrides import apply_transcriptx_env


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    cfg_dir = tmp_path / ".transcriptx"
    monkeypatch.setattr(config_persistence, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config_persistence, "CONFIG_DRAFTS_DIR", cfg_dir / "drafts")
    return cfg_dir


def test_acts_env_model_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSCRIPTX_ACTS_MODEL", "env-bert-model")
    cfg = TranscriptXConfig()
    apply_transcriptx_env(cfg)
    assert cfg.analysis.acts.ml_model_name == "env-bert-model"
    monkeypatch.delenv("TRANSCRIPTX_ACTS_MODEL", raising=False)


def test_acts_env_target_on_pydantic_model() -> None:
    assert "ml_model_name" in ActsSettingsModel.model_fields


def test_acts_invalid_method_fails_validation() -> None:
    errors = validate_config({"analysis": {"acts": {"method": "transformer"}}})
    assert "analysis.acts.method" in errors


def test_acts_invalid_context_window_type_fails_validation() -> None:
    errors = validate_config({"analysis": {"acts": {"context_window_type": "rolling"}}})
    assert "analysis.acts.context_window_type" in errors


def test_acts_out_of_range_confidence_fails_validation() -> None:
    errors = validate_config({"analysis": {"acts": {"min_confidence": 1.5}}})
    assert "analysis.acts.min_confidence" in errors


def test_acts_out_of_range_weight_fails_validation() -> None:
    errors = validate_config({"analysis": {"acts": {"ensemble_weight_ml": -0.1}}})
    assert "analysis.acts.ensemble_weight_ml" in errors


def test_acts_project_method_override_resolves(config_dir, monkeypatch) -> None:
    monkeypatch.delenv("TRANSCRIPTX_ACTS_MODEL", raising=False)
    save_project_config({"analysis": {"acts": {"method": "rules"}}})
    resolved = resolve_effective_config(run_dir=None)
    assert resolved.effective_config.analysis.acts.method == "rules"
    assert resolved.sources_by_key.get("analysis.acts.method") == "project"


def test_acts_profile_payload_roundtrip(config_dir, monkeypatch) -> None:
    monkeypatch.delenv("TRANSCRIPTX_ACTS_MODEL", raising=False)
    save_project_config(
        {
            "analysis": {
                "active_acts_profile": "team",
                "acts": {
                    "method": "ml",
                    "ml_model_name": "profile-bert",
                    "min_confidence": 0.75,
                    "context_window_type": "fixed",
                },
            }
        }
    )
    resolved = resolve_effective_config(run_dir=None)
    acts = resolved.effective_config.analysis.acts
    assert acts.method == "ml"
    assert acts.ml_model_name == "profile-bert"
    assert acts.min_confidence == 0.75
    assert acts.context_window_type == "fixed"
    assert resolved.effective_config.analysis.active_acts_profile == "team"
