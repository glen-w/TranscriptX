"""Integration tests for llm.* config resolution and validation."""

from __future__ import annotations

import json

import pytest

from transcriptx.core.llm.prompting import prompt_envelope_min_chars
from transcriptx.core.config import (
    resolve_effective_config,
    save_project_config,
    validate_config,
)
from transcriptx.core.config import persistence as config_persistence
from transcriptx.core.config.models.llm import LLMSettingsModel
from transcriptx.core.config.persistence import save_run_override
from transcriptx.core.utils.config.config_errors import ConfigLoadError
from transcriptx.core.utils.config.config_raw_validation import validate_raw_config_dict
from transcriptx.core.utils.config.env_overrides import apply_transcriptx_env
from transcriptx.core.utils.config.file_overrides import load_config_file_into
from transcriptx.core.utils.config.main import TranscriptXConfig


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    cfg_dir = tmp_path / ".transcriptx"
    monkeypatch.setattr(config_persistence, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config_persistence, "CONFIG_DRAFTS_DIR", cfg_dir / "drafts")
    return cfg_dir


def test_llm_env_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSCRIPTX_LLM_ENABLED", "1")
    cfg = TranscriptXConfig()
    apply_transcriptx_env(cfg)
    assert cfg.llm.enabled is True
    monkeypatch.delenv("TRANSCRIPTX_LLM_ENABLED", raising=False)


def test_llm_env_target_on_pydantic_model() -> None:
    assert "provider" in LLMSettingsModel.model_fields


def test_llm_invalid_provider_fails_validation() -> None:
    errors = validate_config({"llm": {"provider": "openai"}})
    assert "llm.provider" in errors


def test_llm_max_input_chars_below_floor_fails_validation() -> None:
    floor = prompt_envelope_min_chars()
    errors = validate_config({"llm": {"max_input_chars": floor - 1}})
    assert "llm.max_input_chars" in errors


def test_llm_max_input_chars_at_floor_accepts() -> None:
    floor = prompt_envelope_min_chars()
    errors = validate_config({"llm": {"max_input_chars": floor}})
    assert "llm.max_input_chars" not in errors


def test_llm_max_input_chars_above_floor_accepts() -> None:
    floor = prompt_envelope_min_chars()
    errors = validate_config({"llm": {"max_input_chars": floor + 100}})
    assert "llm.max_input_chars" not in errors


def test_raw_and_validate_config_reject_same_invalid_max_input_chars(tmp_path) -> None:
    floor = prompt_envelope_min_chars()
    payload = {"llm": {"max_input_chars": floor - 1}}
    with pytest.raises(ConfigLoadError, match="max_input_chars"):
        validate_raw_config_dict(payload)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ConfigLoadError, match="max_input_chars"):
        load_config_file_into(TranscriptXConfig(), str(path))
    errors = validate_config(payload)
    assert "llm.max_input_chars" in errors


def test_llm_project_override_resolves(config_dir, monkeypatch) -> None:
    for name in (
        "TRANSCRIPTX_LLM_ENABLED",
        "TRANSCRIPTX_LLM_PROVIDER",
        "TRANSCRIPTX_LLM_MODEL",
        "TRANSCRIPTX_LLM_BASE_URL",
        "TRANSCRIPTX_LLM_SEED",
    ):
        monkeypatch.delenv(name, raising=False)
    save_project_config(
        {"llm": {"enabled": True, "provider": "ollama", "model": "qwen3:8b"}}
    )
    resolved = resolve_effective_config(run_dir=None)
    assert resolved.effective_config.llm.enabled is True
    assert resolved.effective_config.llm.provider == "ollama"
    assert resolved.effective_config.llm.model == "qwen3:8b"
    assert resolved.sources_by_key.get("llm.enabled") == "project"


def test_llm_run_override_wins(config_dir, tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("TRANSCRIPTX_LLM_MODEL", raising=False)
    run_dir = tmp_path / "run1"
    run_dir.mkdir()
    save_project_config({"llm": {"model": "gemma3:12b"}})
    save_run_override(run_dir, {"llm": {"model": "qwen3:4b"}})
    resolved = resolve_effective_config(run_dir=run_dir)
    assert resolved.effective_config.llm.model == "qwen3:4b"
