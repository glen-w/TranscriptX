"""Tests for get_llm_client factory."""

from __future__ import annotations

import pytest

from transcriptx.core.llm import (
    LLMConfigurationError,
    NullLLMClient,
    OllamaClient,
    get_llm_client,
    normalize_base_url,
)
from transcriptx.core.utils.config.main import TranscriptXConfig


@pytest.mark.unit
def test_factory_disabled_returns_null() -> None:
    cfg = TranscriptXConfig()
    cfg.llm.enabled = False
    cfg.llm.provider = "ollama"
    assert isinstance(get_llm_client(cfg), NullLLMClient)


@pytest.mark.unit
def test_factory_null_provider_returns_null() -> None:
    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "null"
    assert isinstance(get_llm_client(cfg), NullLLMClient)


@pytest.mark.unit
def test_factory_ollama_returns_client() -> None:
    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "ollama"
    cfg.llm.model = "qwen3:8b"
    client = get_llm_client(cfg)
    assert isinstance(client, OllamaClient)
    assert client.model == "qwen3:8b"


@pytest.mark.unit
def test_factory_default_model_and_base_url() -> None:
    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "ollama"
    cfg.llm.base_url = "http://localhost:11434/"
    client = get_llm_client(cfg)
    assert isinstance(client, OllamaClient)
    assert client.model == "qwen3:8b"
    assert client.base_url == normalize_base_url("http://localhost:11434/")


@pytest.mark.unit
def test_factory_unsupported_provider_raises() -> None:
    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "unknown"
    with pytest.raises(LLMConfigurationError):
        get_llm_client(cfg)


@pytest.mark.unit
def test_factory_openai_raises() -> None:
    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "openai"
    with pytest.raises(LLMConfigurationError):
        get_llm_client(cfg)
