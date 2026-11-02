"""SR-06: LLM hosts default to loopback / host.docker.internal."""

from __future__ import annotations

import pytest

from transcriptx.core.llm.errors import LLMConfigurationError
from transcriptx.core.llm.ollama_client import (
    llm_host_is_allowed,
    _validate_client_config,
)


def test_loopback_hosts_allowed() -> None:
    assert llm_host_is_allowed("localhost")
    assert llm_host_is_allowed("127.0.0.1")
    assert llm_host_is_allowed("host.docker.internal")
    assert not llm_host_is_allowed("evil.example")
    assert llm_host_is_allowed("evil.example", allow_remote=True)


def test_validate_rejects_remote_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TRANSCRIPTX_LLM_ALLOW_REMOTE_HOST", raising=False)
    monkeypatch.setenv("TRANSCRIPTX_LLM_ALLOW_REMOTE_HOST", "0")
    with pytest.raises(LLMConfigurationError, match="loopback"):
        _validate_client_config(
            base_url="https://api.example/v1",
            model="x",
            request_timeout=1.0,
            availability_timeout=1.0,
            max_output_tokens=16,
        )


def test_validate_allows_remote_when_opted_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSCRIPTX_LLM_ALLOW_REMOTE_HOST", "1")
    _validate_client_config(
        base_url="https://api.example/v1",
        model="x",
        request_timeout=1.0,
        availability_timeout=1.0,
        max_output_tokens=16,
    )
