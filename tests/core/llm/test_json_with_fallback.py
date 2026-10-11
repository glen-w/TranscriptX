"""Unit tests for primary→secondary JSON generate + breaker."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from transcriptx.core.llm.errors import LLMResponseError
from transcriptx.core.llm.json_with_fallback import (
    JsonFallbackLLMClient,
    begin_json_fallback_scope,
    end_json_fallback_scope,
    get_last_json_generate_outcome,
    preferred_json_breaker_tripped,
    reset_json_fallback_scope,
)
from transcriptx.core.llm.ollama_client import OllamaClient


class _FakeOllama(OllamaClient):
    def __init__(self, model: str, responses: list[Any]) -> None:
        # Skip real __init__ validation path by setting attrs directly.
        self._model = model
        self._base_url = "http://localhost:11434"
        self._seed = 42
        self._request_timeout = 30.0
        self._availability_timeout = 1.0
        self._max_output_tokens = 128
        self._tags_cache = None
        self._metrics_sink = SimpleNamespace(
            record_generate=lambda **kwargs: None
        )
        self._effort = None
        self._responses = list(responses)
        self.calls = 0

    def generate(self, **kwargs):  # type: ignore[override]
        self.calls += 1
        if not self._responses:
            raise AssertionError(f"unexpected call to {self._model}")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def is_available(self) -> bool:
        return True


@pytest.fixture(autouse=True)
def _clear_breaker():
    reset_json_fallback_scope()
    yield
    reset_json_fallback_scope()


def test_fallback_used_when_preferred_empty() -> None:
    primary = _FakeOllama("qwen3.8:latest", [LLMResponseError("empty")])
    secondary = _FakeOllama("gemma3:12b", ['{"ok": true}'])
    client = JsonFallbackLLMClient(primary, secondary)
    text = client.generate(
        prompt="x", temperature=0.1, response_format="json"
    )
    assert text == '{"ok": true}'
    assert primary.calls == 1
    assert secondary.calls == 1
    outcome = get_last_json_generate_outcome()
    assert outcome is not None
    assert outcome.used_fallback
    assert outcome.model == "gemma3:12b"


def test_unusable_json_triggers_fallback() -> None:
    primary = _FakeOllama("qwen3.8:latest", ["not-json"])
    secondary = _FakeOllama("gemma3:12b", ['{"a": 1}'])
    client = JsonFallbackLLMClient(primary, secondary)
    text = client.generate(
        prompt="x", temperature=0.1, response_format="json"
    )
    assert text == '{"a": 1}'
    assert get_last_json_generate_outcome().used_fallback  # type: ignore[union-attr]


def test_breaker_skips_preferred_after_threshold() -> None:
    token = begin_json_fallback_scope(
        preferred_model="qwen3.8:latest",
        fallback_model="gemma3:12b",
        threshold=2,
    )
    try:
        primary = _FakeOllama(
            "qwen3.8:latest",
            [LLMResponseError("e1"), LLMResponseError("e2"), LLMResponseError("e3")],
        )
        secondary = _FakeOllama(
            "gemma3:12b", ['{"n": 1}', '{"n": 2}', '{"n": 3}']
        )
        client = JsonFallbackLLMClient(primary, secondary)
        client.generate(prompt="1", temperature=0.0, response_format="json")
        client.generate(prompt="2", temperature=0.0, response_format="json")
        assert preferred_json_breaker_tripped()
        client.generate(prompt="3", temperature=0.0, response_format="json")
        assert primary.calls == 2
        assert secondary.calls == 3
    finally:
        end_json_fallback_scope(token)


def test_plain_text_skips_fallback() -> None:
    primary = _FakeOllama("qwen3.8:latest", ["hello"])
    secondary = _FakeOllama("gemma3:12b", ["nope"])
    client = JsonFallbackLLMClient(primary, secondary)
    assert client.generate(prompt="x", temperature=0.1) == "hello"
    assert secondary.calls == 0
