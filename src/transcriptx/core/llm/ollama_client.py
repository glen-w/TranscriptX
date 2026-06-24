"""Ollama HTTP client (stdlib urllib, no extra dependencies)."""

from __future__ import annotations

import json
import re
import socket
import urllib.error
import urllib.request
from typing import Any, Optional
from urllib.parse import urlparse

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from transcriptx.core.llm.errors import (
    LLMConfigurationError,
    LLMGenerationError,
    LLMModelMissingError,
    LLMResponseError,
    LLMTimeoutError,
    LLMUnavailableError,
    _RetryableTransient,
)
from transcriptx.core.llm.llm_client import LLMClient

_DEFAULT_MAX_ATTEMPTS = 3
_DEFAULT_BACKOFF_MAX = 2
_MODEL_NOT_FOUND_RE = re.compile(r"model\b.*\bnot found", re.IGNORECASE)


def normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def _validate_client_config(
    *,
    base_url: str,
    model: str,
    request_timeout: float,
    availability_timeout: float,
    max_output_tokens: Optional[int],
) -> None:
    if not model or not str(model).strip():
        raise LLMConfigurationError("LLM model must be a non-empty string")
    if not base_url or not str(base_url).strip():
        raise LLMConfigurationError("LLM base_url must be a non-empty string")
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"}:
        raise LLMConfigurationError("LLM base_url must use http or https")
    if request_timeout <= 0:
        raise LLMConfigurationError("LLM request_timeout must be positive")
    if availability_timeout <= 0:
        raise LLMConfigurationError("LLM availability_timeout must be positive")
    if max_output_tokens is not None and max_output_tokens <= 0:
        raise LLMConfigurationError("LLM max_output_tokens must be positive when set")


def _read_http_error_body(exc: urllib.error.HTTPError) -> str:
    try:
        return exc.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


def _is_model_not_found_body(body: str, model: str) -> bool:
    if not body.strip():
        return False
    if model and model in body and _MODEL_NOT_FOUND_RE.search(body):
        return True
    return bool(_MODEL_NOT_FOUND_RE.search(body))


def _http_error_to_exception(
    exc: urllib.error.HTTPError,
    *,
    model: str,
) -> Exception:
    status = exc.code
    if status == 404:
        body = _read_http_error_body(exc)
        if _is_model_not_found_body(body, model):
            return LLMModelMissingError(f"Ollama model not found (HTTP 404): {model!r}")
        return LLMGenerationError(f"Ollama HTTP error 404: {exc.reason}")
    if 400 <= status < 500:
        return LLMGenerationError(f"Ollama HTTP error {status}: {exc.reason}")
    if status >= 500:
        return _RetryableTransient(exc, http_status=status)
    return LLMGenerationError(f"Ollama HTTP error {status}: {exc.reason}")


def _is_timeout_error(exc: object) -> bool:
    if isinstance(exc, TimeoutError):
        return True
    if isinstance(exc, socket.timeout):
        return True
    return False


def _unwrap_timeout(exc: Exception) -> bool:
    if _is_timeout_error(exc):
        return True
    if isinstance(exc, urllib.error.URLError):
        return _is_timeout_error(exc.reason)
    return False


class OllamaClient(LLMClient):
    """Local Ollama client using ``/api/generate``."""

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:11434",
        model: str = "qwen3:8b",
        seed: int = 42,
        request_timeout: float = 120.0,
        availability_timeout: float = 5.0,
        max_output_tokens: Optional[int] = 2048,
    ) -> None:
        _validate_client_config(
            base_url=base_url,
            model=model,
            request_timeout=request_timeout,
            availability_timeout=availability_timeout,
            max_output_tokens=max_output_tokens,
        )
        self._base_url = normalize_base_url(base_url)
        self._model = model
        self._seed = seed
        self._request_timeout = request_timeout
        self._availability_timeout = availability_timeout
        self._max_output_tokens = max_output_tokens
        self._tags_cache: Optional[dict[str, Any]] = None

    @property
    def model(self) -> str:
        return self._model

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def tags_cache(self) -> Optional[dict[str, Any]]:
        """Cached ``/api/tags`` payload when ``is_available()`` has been called."""
        return self._tags_cache

    def is_available(self) -> bool:
        """Return True when the Ollama daemon responds to ``GET /api/tags``."""
        try:
            raw = self._http_get("/api/tags", timeout=self._availability_timeout)
            data = json.loads(raw)
            if isinstance(data, dict):
                self._tags_cache = data
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
    ) -> str:
        if temperature < 0 or temperature > 2:
            raise LLMConfigurationError("LLM temperature must be between 0 and 2")

        body: dict[str, Any] = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "seed": self._seed,
            },
        }
        if system_prompt is not None:
            body["system"] = system_prompt
        num_predict = max_tokens if max_tokens is not None else self._max_output_tokens
        if num_predict is not None:
            body["options"]["num_predict"] = num_predict

        raw = self._post_generate_with_retry(body)
        try:
            data = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise LLMResponseError(f"Ollama returned non-JSON body: {exc}") from exc

        if not isinstance(data, dict):
            raise LLMResponseError("Ollama response JSON must be an object")

        response_text = data.get("response")
        if not isinstance(response_text, str) or not response_text.strip():
            raise LLMResponseError("Ollama response missing non-empty 'response' field")

        return response_text

    def _post_generate_with_retry(self, body: dict[str, Any]) -> str:
        try:
            return self._execute_generate_request(body)
        except _RetryableTransient as exc:
            self._raise_from_transient(exc)
            raise  # pragma: no cover

    @retry(
        retry=retry_if_exception_type(_RetryableTransient),
        stop=stop_after_attempt(_DEFAULT_MAX_ATTEMPTS),
        wait=wait_exponential(multiplier=0.25, max=_DEFAULT_BACKOFF_MAX),
        reraise=True,
    )
    def _execute_generate_request(self, body: dict[str, Any]) -> str:
        try:
            return self._http_post("/api/generate", body, timeout=self._request_timeout)
        except _RetryableTransient:
            raise
        except (
            LLMUnavailableError,
            LLMModelMissingError,
            LLMTimeoutError,
            LLMResponseError,
            LLMGenerationError,
            LLMConfigurationError,
        ):
            raise
        except Exception as exc:
            wrapped = self._wrap_network_error(exc)
            if isinstance(wrapped, _RetryableTransient):
                raise wrapped
            raise wrapped

    def _raise_from_transient(self, exc: _RetryableTransient) -> None:
        cause = exc.cause
        if isinstance(cause, urllib.error.HTTPError):
            status = cause.code
            if status == 404:
                body = _read_http_error_body(cause)
                if _is_model_not_found_body(body, self._model):
                    raise LLMModelMissingError(
                        f"Ollama model not found (HTTP 404): {self._model!r}"
                    ) from cause
                raise LLMGenerationError(
                    f"Ollama HTTP error 404: {cause.reason}"
                ) from cause
            raise LLMGenerationError(
                f"Ollama HTTP error {status}: {cause.reason}"
            ) from cause
        if _unwrap_timeout(cause):
            raise LLMTimeoutError("Ollama request timed out") from cause
        raise LLMUnavailableError("Ollama service is unreachable") from cause

    def _http_get(self, path: str, *, timeout: float) -> str:
        url = f"{self._base_url}{path}"
        req = urllib.request.Request(url, method="GET")
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
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8")
        except Exception as exc:
            raise self._wrap_network_error(exc) from exc

    def _wrap_network_error(self, exc: Exception) -> Exception:
        if isinstance(exc, urllib.error.HTTPError):
            return _http_error_to_exception(exc, model=self._model)

        if isinstance(exc, urllib.error.URLError):
            reason = exc.reason
            if _unwrap_timeout(exc):
                return _RetryableTransient(exc)
            if isinstance(reason, ConnectionRefusedError):
                return _RetryableTransient(exc)
            if isinstance(reason, OSError):
                return _RetryableTransient(exc)
            return _RetryableTransient(exc)

        if isinstance(exc, socket.timeout):
            return _RetryableTransient(exc)

        if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
            return _RetryableTransient(exc)

        return exc
