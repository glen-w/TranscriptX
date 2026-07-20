"""Unit tests for chart_descriptions LLM client timeout capping."""

from __future__ import annotations

from transcriptx.core.analysis.chart_descriptions.generate import (
    _client_with_request_timeout,
)
from transcriptx.core.llm import NullLLMClient, OllamaClient


def test_client_with_request_timeout_caps_ollama_client() -> None:
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="qwen3:8b",
        request_timeout=1350.0,
        availability_timeout=1.0,
    )
    capped = _client_with_request_timeout(client, 120.0)
    assert isinstance(capped, OllamaClient)
    assert capped._request_timeout == 120.0
    assert capped.model == client.model
    assert capped.base_url == client.base_url


def test_client_with_request_timeout_leaves_shorter_timeout() -> None:
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="qwen3:8b",
        request_timeout=30.0,
        availability_timeout=1.0,
    )
    same = _client_with_request_timeout(client, 120.0)
    assert same is client


def test_client_with_request_timeout_ignores_null_client() -> None:
    client = NullLLMClient()
    assert _client_with_request_timeout(client, 120.0) is client
