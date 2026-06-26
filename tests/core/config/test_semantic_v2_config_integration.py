"""Integration tests for semantic_similarity_v2 config resolution and persistence."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from transcriptx.core.config import (
    get_default_config_dict,
    resolve_effective_config,
    save_project_config,
    validate_config,
)
from transcriptx.core.config import persistence as config_persistence
from transcriptx.core.config.models.semantic_similarity_v2 import (
    SemanticSimilarityV2SettingsModel,
)
from transcriptx.core.config.persistence import save_run_override
from transcriptx.core.utils.config import TranscriptXConfig
from transcriptx.core.utils.config.env_overrides import apply_transcriptx_env


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    cfg_dir = tmp_path / ".transcriptx"
    monkeypatch.setattr(config_persistence, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config_persistence, "CONFIG_DRAFTS_DIR", cfg_dir / "drafts")
    return cfg_dir


def test_project_override_v2_resolves(config_dir) -> None:
    save_project_config({"analysis": {"semantic_similarity_v2": {"batch_size": 32}}})
    resolved = resolve_effective_config(run_dir=None)
    assert resolved.effective_config.analysis.semantic_similarity_v2.batch_size == 32
    assert (
        resolved.sources_by_key.get("analysis.semantic_similarity_v2.batch_size")
        == "project"
    )


def test_run_override_v2_wins_over_project(config_dir, tmp_path) -> None:
    run_dir = tmp_path / "out" / "run1"
    run_dir.mkdir(parents=True)
    save_project_config({"analysis": {"semantic_similarity_v2": {"batch_size": 32}}})
    save_run_override(
        run_dir, {"analysis": {"semantic_similarity_v2": {"batch_size": 16}}}
    )
    resolved = resolve_effective_config(run_dir=run_dir)
    assert resolved.effective_config.analysis.semantic_similarity_v2.batch_size == 16
    assert (
        resolved.sources_by_key.get("analysis.semantic_similarity_v2.batch_size")
        == "run"
    )


def test_v2_roundtrip_save_load(config_dir) -> None:
    config = TranscriptXConfig()
    config.analysis.semantic_similarity_v2.self_similarity_threshold = 0.81
    save_project_config(config.to_dict())
    resolved = resolve_effective_config(run_dir=None)
    assert (
        resolved.effective_config.analysis.semantic_similarity_v2.self_similarity_threshold
        == 0.81
    )


def test_draft_override_v2_validates() -> None:
    errors = validate_config(
        {"analysis": {"semantic_similarity_v2": {"batch_size": 0}}}
    )
    assert "analysis.semantic_similarity_v2.batch_size" in errors


def test_env_semantic_v2_model_applies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSCRIPTX_SEMANTIC_V2_MODEL", "custom/model")
    with patch("transcriptx.core.config.resolver.load_project_config", return_value={}):
        with patch(
            "transcriptx.core.config.resolver.load_draft_override", return_value={}
        ):
            resolved = resolve_effective_config(run_dir=None)
    assert (
        resolved.effective_config.analysis.semantic_similarity_v2.model_name
        == "custom/model"
    )
    monkeypatch.delenv("TRANSCRIPTX_SEMANTIC_V2_MODEL", raising=False)


def test_env_target_path_in_pydantic_model() -> None:
    assert "model_name" in SemanticSimilarityV2SettingsModel.model_fields


def test_apply_transcriptx_semantic_v2_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSCRIPTX_SEMANTIC_V2_MODEL", "env/model")
    cfg = TranscriptXConfig()
    apply_transcriptx_env(cfg)
    assert cfg.analysis.semantic_similarity_v2.model_name == "env/model"
    monkeypatch.delenv("TRANSCRIPTX_SEMANTIC_V2_MODEL", raising=False)


def test_full_default_config_validates_clean() -> None:
    errors = validate_config(get_default_config_dict())
    assert "metadata.duration_calculation" not in errors
    assert "dashboard.duration_summary_style" not in errors
    v2_errors = {
        k: v
        for k, v in errors.items()
        if k.startswith("analysis.semantic_similarity_v2.")
    }
    assert v2_errors == {}
