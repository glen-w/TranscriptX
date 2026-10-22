"""Unit tests for the OpenAI-compatible Chat Completions client."""

from __future__ import annotations

import pytest

import transcriptx.core.llm.openai_compatible_client as occ
from transcriptx.core.llm import (
    LLMConfigurationError,
    OpenAICompatibleClient,
    get_llm_client,
)
from transcriptx.core.llm.openai_compatible_client import (
    openai_response_format,
    resolve_openai_api_key,
)
from transcriptx.core.utils.config.main import TranscriptXConfig


def test_normalize_base_url_appends_v1() -> None:
    from transcriptx.core.llm.openai_compatible_client import normalize_openai_base_url

    assert (
        normalize_openai_base_url("http://127.0.0.1:4000") == "http://127.0.0.1:4000/v1"
    )
    assert (
        normalize_openai_base_url("http://127.0.0.1:4000/v1/")
        == "http://127.0.0.1:4000/v1"
    )


def test_normalize_base_url_requires_explicit_host() -> None:
    from transcriptx.core.llm.openai_compatible_client import normalize_openai_base_url

    with pytest.raises(LLMConfigurationError, match="no silent cloud"):
        normalize_openai_base_url("")


def test_response_format_json_and_schema() -> None:
    assert openai_response_format(None) is None
    assert openai_response_format("json") == {"type": "json_object"}
    mapped = openai_response_format({"type": "object", "properties": {}})
    assert mapped["type"] == "json_schema"
    assert mapped["json_schema"]["schema"]["type"] == "object"


def test_resolve_api_key_prefers_transcriptx_env(monkeypatch) -> None:
    monkeypatch.setenv("TRANSCRIPTX_LLM_API_KEY", "tx-key")
    monkeypatch.setenv("OPENAI_API_KEY", "oa-key")
    assert resolve_openai_api_key() == "tx-key"
    monkeypatch.delenv("TRANSCRIPTX_LLM_API_KEY")
    assert resolve_openai_api_key() == "oa-key"


def test_factory_openai_compatible(monkeypatch) -> None:
    monkeypatch.delenv("TRANSCRIPTX_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "openai_compatible"
    cfg.llm.model = "gpt-4o-mini"
    cfg.llm.base_url = "http://127.0.0.1:4000"
    client = get_llm_client(cfg)
    assert isinstance(client, OpenAICompatibleClient)
    assert client.model == "gpt-4o-mini"
    assert client.base_url.endswith("/v1")


def test_factory_openai_compatible_requires_base_url() -> None:
    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "openai_compatible"
    cfg.llm.model = "local-model"
    cfg.llm.base_url = None
    with pytest.raises(LLMConfigurationError, match="base_url"):
        get_llm_client(cfg)


def test_generate_posts_chat_completions(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _Resp:
        def read(self):
            return b'{"choices":[{"message":{"content":"{\\"ok\\":true}"}}]}'

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    def _urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["timeout"] = timeout
        captured["body"] = req.data
        captured["authorization"] = req.get_header("Authorization")
        return _Resp()

    monkeypatch.setattr(occ.urllib.request, "urlopen", _urlopen)
    monkeypatch.setenv("TRANSCRIPTX_LLM_API_KEY", "secret")
    client = OpenAICompatibleClient(
        base_url="http://127.0.0.1:4000/v1",
        model="local-model",
        api_key="secret",
        request_timeout=12.0,
        availability_timeout=2.0,
    )
    text = client.generate(
        prompt="hi",
        system_prompt="sys",
        temperature=0.2,
        response_format="json",
    )
    assert text == '{"ok":true}'
    assert captured["url"] == "http://127.0.0.1:4000/v1/chat/completions"
    import json

    body = json.loads(captured["body"])
    assert body["model"] == "local-model"
    assert body["response_format"] == {"type": "json_object"}
    assert body["messages"][0]["role"] == "system"
    assert captured["authorization"] == "Bearer secret"


def test_is_available_hits_models(monkeypatch) -> None:
    urls: list[str] = []

    class _Resp:
        def read(self):
            return b'{"data":[]}'

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    def _urlopen(req, timeout=None):
        urls.append(req.full_url)
        return _Resp()

    monkeypatch.setattr(occ.urllib.request, "urlopen", _urlopen)
    client = OpenAICompatibleClient(
        base_url="http://127.0.0.1:4000",
        model="m",
        api_key="",
    )
    assert client.is_available() is True
    assert urls == ["http://127.0.0.1:4000/v1/models"]


def test_is_available_false_on_error(monkeypatch) -> None:
    def _urlopen(*_a, **_k):
        raise TimeoutError("nope")

    monkeypatch.setattr(occ.urllib.request, "urlopen", _urlopen)
    client = OpenAICompatibleClient(base_url="http://127.0.0.1:9", model="m")
    assert client.is_available() is False


def test_base_url_is_loopback() -> None:
    from transcriptx.core.llm.openai_compatible_client import base_url_is_loopback

    assert base_url_is_loopback("http://127.0.0.1:4000/v1")
    assert base_url_is_loopback("http://localhost:8000")
    assert not base_url_is_loopback("https://api.openai.com/v1")


def test_remote_privacy_caption() -> None:
    from transcriptx.core.llm.openai_compatible_client import (
        remote_llm_privacy_caption,
    )

    assert remote_llm_privacy_caption("http://127.0.0.1:4000") is None
    assert "not Local AI" in (
        remote_llm_privacy_caption("https://api.openai.com/v1") or ""
    )
    assert "base_url" in (remote_llm_privacy_caption("") or "")
