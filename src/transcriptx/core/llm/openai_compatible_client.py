"""OpenAI-compatible Chat Completions client (stdlib urllib).

Opt-in only. Never defaults ``base_url`` to a cloud host. API keys are read from
the environment and are never stored on ``LLMSettingsModel``.
"""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from typing import Any, Mapping, Optional
from urllib.parse import urlparse

from transcriptx.core.llm.errors import (
    LLMConfigurationError,
    LLMGenerationError,
    LLMResponseError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from transcriptx.core.llm.llm_client import LLMClient

_API_KEY_ENV = "TRANSCRIPTX_LLM_API_KEY"
_API_KEY_FALLBACK_ENV = "OPENAI_API_KEY"


def resolve_openai_api_key() -> str:
    """Operator-supplied key. Empty is allowed for loopback servers without auth."""
    return (
        os.environ.get(_API_KEY_ENV, "").strip()
        or os.environ.get(_API_KEY_FALLBACK_ENV, "").strip()
    )


def normalize_openai_base_url(base_url: str) -> str:
    url = (base_url or "").strip().rstrip("/")
    if not url:
        raise LLMConfigurationError(
            "openai_compatible requires llm.base_url "
            "(do not omit it — there is no silent cloud default)."
        )
    if url.endswith("/v1"):
        return url
    return url + "/v1"


def openai_response_format(
    response_format: Optional[str | Mapping[str, Any]],
) -> dict[str, Any] | None:
    """Map TranscriptX ``response_format`` onto Chat Completions ``response_format``."""
    if response_format is None:
        return None
    if isinstance(response_format, str):
        if response_format != "json":
            raise LLMConfigurationError(
                "LLM response_format must be None, 'json', or a JSON Schema object"
            )
        return {"type": "json_object"}
    if not isinstance(response_format, Mapping) or not response_format:
        raise LLMConfigurationError(
            "LLM response_format must be None, 'json', or a JSON Schema object"
        )
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "transcriptx",
            "schema": dict(response_format),
        },
    }


class OpenAICompatibleClient(LLMClient):
    """POST ``/v1/chat/completions`` against an OpenAI-compatible endpoint."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str = "",
        seed: int = 42,
        request_timeout: float = 1350.0,
        availability_timeout: float = 7.5,
        max_output_tokens: Optional[int] = 2048,
    ) -> None:
        if not (model or "").strip():
            raise LLMConfigurationError("openai_compatible requires llm.model")
        if request_timeout <= 0 or availability_timeout <= 0:
            raise LLMConfigurationError("LLM timeouts must be positive")
        self._base_url = normalize_openai_base_url(base_url)
        self._model = model.strip()
        self._api_key = (api_key or "").strip()
        self._seed = seed
        self._request_timeout = request_timeout
        self._availability_timeout = availability_timeout
        self._max_output_tokens = max_output_tokens

    @property
    def model(self) -> str:
        return self._model

    @property
    def base_url(self) -> str:
        return self._base_url

    def is_available(self) -> bool:
        try:
            self._http_get("/models", timeout=self._availability_timeout)
            return True
        except Exception:
            return False

    def generate(
        self,
        *,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float,
        max_tokens: Optional[int] = None,
        response_format: Optional[str | Mapping[str, Any]] = None,
        think: bool | str | None = None,
    ) -> str:
        del think  # Ollama-only; ignored on OpenAI-compatible endpoints.
        if temperature < 0 or temperature > 2:
            raise LLMConfigurationError("LLM temperature must be between 0 and 2")
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        body: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "seed": self._seed,
        }
        mapped = openai_response_format(response_format)
        if mapped is not None:
            body["response_format"] = mapped
        num_predict = max_tokens if max_tokens is not None else self._max_output_tokens
        if num_predict is not None:
            body["max_tokens"] = num_predict
        try:
            raw = self._http_post(
                "/chat/completions", body, timeout=self._request_timeout
            )
        except LLMTimeoutError:
            raise
        except LLMUnavailableError:
            raise
        except LLMGenerationError:
            raise
        except LLMConfigurationError:
            raise
        try:
            data = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise LLMResponseError(
                f"OpenAI-compatible endpoint returned non-JSON body: {exc}"
            ) from exc
        if not isinstance(data, dict):
            raise LLMResponseError("OpenAI-compatible response JSON must be an object")
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMResponseError("OpenAI-compatible response missing choices")
        first = choices[0] if isinstance(choices[0], dict) else {}
        message = first.get("message") if isinstance(first.get("message"), dict) else {}
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise LLMResponseError(
                "OpenAI-compatible response missing non-empty message.content"
            )
        return content

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _http_get(self, path: str, *, timeout: float) -> str:
        url = f"{self._base_url}{path}"
        req = urllib.request.Request(url, method="GET", headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8")
        except Exception as exc:
            raise self._wrap_network_error(exc) from exc

    def _http_post(self, path: str, body: dict[str, Any], *, timeout: float) -> str:
        url = f"{self._base_url}{path}"
        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            method="POST",
            headers=self._headers(),
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8")
        except Exception as exc:
            raise self._wrap_network_error(exc) from exc

    def _wrap_network_error(self, exc: Exception) -> Exception:
        if isinstance(exc, urllib.error.HTTPError):
            return LLMGenerationError(
                f"OpenAI-compatible HTTP error {exc.code}: {exc.reason}"
            )
        if isinstance(exc, urllib.error.URLError):
            if isinstance(exc.reason, socket.timeout) or isinstance(
                exc.reason, TimeoutError
            ):
                return LLMTimeoutError("OpenAI-compatible request timed out")
            return LLMUnavailableError("OpenAI-compatible service is unreachable")
        if isinstance(exc, (socket.timeout, TimeoutError)):
            return LLMTimeoutError("OpenAI-compatible request timed out")
        if isinstance(exc, (ConnectionError, OSError)):
            return LLMUnavailableError("OpenAI-compatible service is unreachable")
        return exc


def build_openai_compatible_client(
    *,
    base_url: str,
    model: str,
    seed: int,
    request_timeout: float,
    availability_timeout: float,
    max_output_tokens: Optional[int],
    api_key: str | None = None,
) -> OpenAICompatibleClient:
    key = api_key if api_key is not None else resolve_openai_api_key()
    return OpenAICompatibleClient(
        base_url=base_url,
        model=model,
        api_key=key,
        seed=seed,
        request_timeout=request_timeout,
        availability_timeout=availability_timeout,
        max_output_tokens=max_output_tokens,
    )


def base_url_is_loopback(base_url: str) -> bool:
    """True when the host is loopback / Docker Desktop bridge (local process)."""
    try:
        host = (urlparse(base_url).hostname or "").strip().lower()
    except ValueError:
        return False
    return host in {"127.0.0.1", "localhost", "::1", "host.docker.internal"}
