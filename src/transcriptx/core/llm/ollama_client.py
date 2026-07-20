"""Ollama HTTP client (stdlib urllib, no extra dependencies)."""

from __future__ import annotations

import json
import re
import socket
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse
from dataclasses import dataclass

from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
import time

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
from transcriptx.core.llm.metrics import (
    LlmMetricsSink,
    get_noop_llm_metrics_sink,
)

_DEFAULT_MAX_ATTEMPTS = 3
_DEFAULT_BACKOFF_MAX = 2
_MODEL_NOT_FOUND_RE = re.compile(r"model\b.*\bnot found", re.IGNORECASE)
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"


def normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def _running_in_docker() -> bool:
    return Path("/.dockerenv").exists()


def resolve_ollama_base_url(base_url: str) -> str:
    """Normalize base URL and remap Docker Desktop bridge hosts on the host OS.

    Project ``.env`` often sets ``http://host.docker.internal:11434`` so the
    containerized GUI can reach Ollama on the Mac/Windows host. When the same
    config is loaded by a host-side Python process, that hostname is usually
    unreachable — rewrite to loopback unless we are inside a container.
    """
    url = normalize_base_url(base_url)
    if "host.docker.internal" not in url:
        return url
    if _running_in_docker():
        return url
    return url.replace("host.docker.internal", "127.0.0.1", 1)


def parse_ollama_tags_payload(payload: Any) -> list[str]:
    """Extract model ``name`` tags from an Ollama ``/api/tags`` JSON payload."""
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return []
    names: list[str] = []
    seen: set[str] = set()
    for row in models:
        if isinstance(row, dict) and isinstance(row.get("name"), str):
            name = row["name"].strip()
            if name and name not in seen:
                seen.add(name)
                names.append(name)
    return names


@dataclass(frozen=True)
class OllamaModelListResult:
    """UI-safe result of listing installed Ollama models."""

    models: tuple[str, ...]
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


def list_installed_ollama_models(
    base_url: str | None = None,
    *,
    timeout: float = 5.0,
) -> OllamaModelListResult:
    """List installed Ollama model tags. Never raises — returns empty + error."""
    url = resolve_ollama_base_url(base_url or DEFAULT_OLLAMA_BASE_URL)
    tags_url = f"{url}/api/tags"
    try:
        req = urllib.request.Request(tags_url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        return OllamaModelListResult(models=tuple(parse_ollama_tags_payload(data)))
    except Exception as exc:  # noqa: BLE001 — UI must not crash on probe failure
        return OllamaModelListResult(
            models=(),
            error=f"Ollama tags probe failed for {tags_url}: {exc}",
        )


def build_ollama_client(
    *,
    model: str,
    seed: int,
    request_timeout: float,
    availability_timeout: float,
    base_url: Optional[str] = None,
    max_output_tokens: Optional[int] = None,
    metrics_sink: Optional[LlmMetricsSink] = None,
    effort: Optional[str] = None,
) -> "OllamaClient":
    """Generic provider-layer factory taking explicit transport parameters.

    Callers (e.g. analysis runtime resolution) own policy such as effort
    profiles; this factory only normalizes the base URL and constructs the
    client.
    """
    return OllamaClient(
        base_url=resolve_ollama_base_url(base_url or DEFAULT_OLLAMA_BASE_URL),
        model=model,
        seed=seed,
        request_timeout=request_timeout,
        availability_timeout=availability_timeout,
        max_output_tokens=max_output_tokens,
        metrics_sink=metrics_sink,
        effort=effort,
    )


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


def _extract_provider_timing(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    mapping = {
        "total_duration": "provider_total_duration_ns",
        "load_duration": "provider_load_duration_ns",
        "prompt_eval_count": "prompt_eval_count",
        "prompt_eval_duration": "prompt_eval_duration_ns",
        "eval_count": "eval_count",
        "eval_duration": "eval_duration_ns",
    }
    for src, dest in mapping.items():
        val = data.get(src)
        if isinstance(val, bool):
            continue
        if isinstance(val, (int, float)) and val >= 0 and val == val:  # not NaN
            out[dest] = int(val)
    return out


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
        request_timeout: float = 1350.0,
        availability_timeout: float = 7.5,
        max_output_tokens: Optional[int] = 2048,
        metrics_sink: Optional[LlmMetricsSink] = None,
        effort: Optional[str] = None,
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
        self._metrics_sink: LlmMetricsSink = metrics_sink or get_noop_llm_metrics_sink()
        self._effort = effort

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
        response_format: Optional[str] = None,
    ) -> str:
        if temperature < 0 or temperature > 2:
            raise LLMConfigurationError("LLM temperature must be between 0 and 2")
        if response_format is not None and response_format not in {"json"}:
            raise LLMConfigurationError(
                "LLM response_format must be None or 'json' for Ollama"
            )

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
        if response_format is not None:
            body["format"] = response_format
        num_predict = max_tokens if max_tokens is not None else self._max_output_tokens
        if num_predict is not None:
            body["options"]["num_predict"] = num_predict

        logical_start = time.perf_counter()
        attempt_exec_ms = 0.0
        attempts = 0
        raw: Optional[str] = None
        try:
            for attempt in Retrying(
                retry=retry_if_exception_type(_RetryableTransient),
                stop=stop_after_attempt(_DEFAULT_MAX_ATTEMPTS),
                wait=wait_exponential(multiplier=0.25, max=_DEFAULT_BACKOFF_MAX),
                reraise=True,
            ):
                with attempt:
                    attempts = attempt.retry_state.attempt_number
                    attempt_start = time.perf_counter()
                    try:
                        raw = self._execute_generate_request_once(body)
                    finally:
                        attempt_exec_ms += (
                            time.perf_counter() - attempt_start
                        ) * 1000.0
        except _RetryableTransient as exc:
            self._emit_metrics(
                success=False,
                retry_count=max(0, attempts - 1),
                logical_wall_ms=(time.perf_counter() - logical_start) * 1000.0,
                attempt_exec_ms=attempt_exec_ms,
            )
            self._raise_from_transient(exc)
            raise
        except Exception:
            self._emit_metrics(
                success=False,
                retry_count=max(0, attempts - 1),
                logical_wall_ms=(time.perf_counter() - logical_start) * 1000.0,
                attempt_exec_ms=attempt_exec_ms,
            )
            raise

        assert raw is not None
        provider_fields: dict[str, Any] = {}
        try:
            data = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            self._emit_metrics(
                success=False,
                retry_count=max(0, attempts - 1),
                logical_wall_ms=(time.perf_counter() - logical_start) * 1000.0,
                attempt_exec_ms=attempt_exec_ms,
            )
            raise LLMResponseError(f"Ollama returned non-JSON body: {exc}") from exc

        if not isinstance(data, dict):
            self._emit_metrics(
                success=False,
                retry_count=max(0, attempts - 1),
                logical_wall_ms=(time.perf_counter() - logical_start) * 1000.0,
                attempt_exec_ms=attempt_exec_ms,
            )
            raise LLMResponseError("Ollama response JSON must be an object")

        provider_fields = _extract_provider_timing(data)
        response_text = data.get("response")
        if not isinstance(response_text, str) or not response_text.strip():
            self._emit_metrics(
                success=False,
                retry_count=max(0, attempts - 1),
                logical_wall_ms=(time.perf_counter() - logical_start) * 1000.0,
                attempt_exec_ms=attempt_exec_ms,
                **provider_fields,
            )
            raise LLMResponseError("Ollama response missing non-empty 'response' field")

        self._emit_metrics(
            success=True,
            retry_count=max(0, attempts - 1),
            logical_wall_ms=(time.perf_counter() - logical_start) * 1000.0,
            attempt_exec_ms=attempt_exec_ms,
            **provider_fields,
        )
        return response_text

    def _emit_metrics(self, **kwargs: Any) -> None:
        try:
            self._metrics_sink.record_generate(
                model=self._model,
                effort=self._effort,
                **kwargs,
            )
        except Exception:
            # Metrics must never break generation.
            return

    def _post_generate_with_retry(self, body: dict[str, Any]) -> str:
        try:
            return self._execute_generate_request_once(body)
        except _RetryableTransient as exc:
            self._raise_from_transient(exc)
            raise  # pragma: no cover

    def _execute_generate_request_once(self, body: dict[str, Any]) -> str:
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
