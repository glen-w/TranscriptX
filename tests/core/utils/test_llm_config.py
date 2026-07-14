"""LLM configuration wiring tests."""

from __future__ import annotations

import json

import pytest

from transcriptx.core.utils.config.config_errors import ConfigLoadError
from transcriptx.core.utils.config.env_overrides import apply_transcriptx_env
from transcriptx.core.utils.config.file_overrides import load_config_file_into
from transcriptx.core.utils.config.main import TranscriptXConfig


@pytest.mark.unit
def test_llm_in_to_dict_round_trip() -> None:
    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "ollama"
    cfg.llm.model = "qwen3:8b"
    cfg.llm.base_url = "http://localhost:11434/"
    cfg.llm.seed = 7
    snapshot = cfg.to_dict()
    assert "llm" in snapshot
    assert snapshot["llm"]["enabled"] is True
    assert snapshot["llm"]["provider"] == "ollama"
    assert snapshot["llm"]["model"] == "qwen3:8b"
    assert snapshot["llm"]["seed"] == 7


@pytest.mark.unit
def test_llm_file_load_and_unknown_nested_key_rejected(tmp_path) -> None:
    cfg = TranscriptXConfig()
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"llm": {"enabled": True, "provider": "ollama", "bogus": 1}}),
        encoding="utf-8",
    )
    with pytest.raises(ConfigLoadError):
        load_config_file_into(cfg, str(path))


@pytest.mark.unit
def test_llm_file_load_applies_values(tmp_path) -> None:
    cfg = TranscriptXConfig()
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "llm": {
                    "enabled": True,
                    "provider": "ollama",
                    "model": "gemma3:12b",
                    "base_url": "http://127.0.0.1:11434/",
                    "max_input_chars": 12000,
                }
            }
        ),
        encoding="utf-8",
    )
    load_config_file_into(cfg, str(path))
    assert cfg.llm.enabled is True
    assert cfg.llm.model == "gemma3:12b"
    assert cfg.llm.max_input_chars == 12000


@pytest.mark.unit
def test_llm_env_overrides(monkeypatch) -> None:
    cfg = TranscriptXConfig()
    monkeypatch.setenv("TRANSCRIPTX_LLM_ENABLED", "1")
    monkeypatch.setenv("TRANSCRIPTX_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("TRANSCRIPTX_LLM_MODEL", "qwen3:4b")
    monkeypatch.setenv("TRANSCRIPTX_LLM_BASE_URL", "http://localhost:11434/")
    monkeypatch.setenv("TRANSCRIPTX_LLM_SEED", "99")
    apply_transcriptx_env(cfg)
    assert cfg.llm.enabled is True
    assert cfg.llm.provider == "ollama"
    assert cfg.llm.model == "qwen3:4b"
    assert cfg.llm.seed == 99


@pytest.mark.unit
def test_llm_env_invalid_provider_warn_skips(monkeypatch) -> None:
    cfg = TranscriptXConfig()
    cfg.llm.provider = "ollama"
    monkeypatch.setenv("TRANSCRIPTX_LLM_PROVIDER", "openai")
    apply_transcriptx_env(cfg)
    assert cfg.llm.provider == "ollama"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("env_name", "file_value", "env_value", "attr", "expected"),
    [
        ("TRANSCRIPTX_LLM_ENABLED", False, "1", "enabled", True),
        ("TRANSCRIPTX_LLM_PROVIDER", "null", "ollama", "provider", "ollama"),
        ("TRANSCRIPTX_LLM_MODEL", "gemma3:12b", "qwen3:8b", "model", "qwen3:8b"),
        (
            "TRANSCRIPTX_LLM_BASE_URL",
            "http://127.0.0.1:11434",
            "http://localhost:11434",
            "base_url",
            "http://localhost:11434",
        ),
        ("TRANSCRIPTX_LLM_SEED", 1, "42", "seed", 42),
        ("TRANSCRIPTX_LLM_REQUEST_TIMEOUT", 30.0, "99.5", "request_timeout", 99.5),
        (
            "TRANSCRIPTX_LLM_AVAILABILITY_TIMEOUT",
            2.0,
            "7.5",
            "availability_timeout",
            7.5,
        ),
        ("TRANSCRIPTX_LLM_MAX_INPUT_CHARS", 12000, "24000", "max_input_chars", 24000),
        ("TRANSCRIPTX_LLM_MAX_OUTPUT_TOKENS", 512, "1024", "max_output_tokens", 1024),
        ("TRANSCRIPTX_LLM_DEFAULT_TEMPERATURE", 0.1, "0.7", "default_temperature", 0.7),
    ],
)
def test_llm_env_overrides_each_key_over_file(
    tmp_path,
    monkeypatch,
    env_name: str,
    file_value,
    env_value: str,
    attr: str,
    expected,
) -> None:
    cfg = TranscriptXConfig()
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"llm": {attr: file_value}}),
        encoding="utf-8",
    )
    load_config_file_into(cfg, str(path))
    monkeypatch.setenv(env_name, env_value)
    apply_transcriptx_env(cfg)
    assert getattr(cfg.llm, attr) == expected


@pytest.mark.unit
def test_llm_max_input_chars_below_minimum_rejected(tmp_path) -> None:
    from transcriptx.core.llm.prompting import prompt_envelope_min_chars

    min_chars = prompt_envelope_min_chars()
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"llm": {"max_input_chars": min_chars - 1}}),
        encoding="utf-8",
    )
    with pytest.raises(ConfigLoadError, match="max_input_chars"):
        load_config_file_into(TranscriptXConfig(), str(path))


@pytest.mark.unit
def test_llm_env_overrides_file_values(tmp_path, monkeypatch) -> None:
    cfg = TranscriptXConfig()
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {"llm": {"enabled": False, "provider": "null", "model": "gemma3:12b"}}
        ),
        encoding="utf-8",
    )
    load_config_file_into(cfg, str(path))
    monkeypatch.setenv("TRANSCRIPTX_LLM_ENABLED", "1")
    monkeypatch.setenv("TRANSCRIPTX_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("TRANSCRIPTX_LLM_MODEL", "qwen3:8b")
    apply_transcriptx_env(cfg)
    assert cfg.llm.enabled is True
    assert cfg.llm.provider == "ollama"
    assert cfg.llm.model == "qwen3:8b"
