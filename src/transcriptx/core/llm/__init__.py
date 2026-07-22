"""
LLM integration for TranscriptX.

This module provides a pluggable interface for LLM providers, enabling
integration with Ollama and other LLM services.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from transcriptx.core.llm.errors import (
    LLM_CONFIGURATION_ERROR,
    LLMConfigurationError,
)
from transcriptx.core.llm.llm_client import LLMClient, NullLLMClient
from transcriptx.core.llm.ollama_client import (
    OllamaClient,
    normalize_base_url,
    resolve_ollama_base_url,
    list_installed_ollama_models,
    OllamaModelListResult,
    parse_ollama_tags_payload,
)
from transcriptx.core.llm.thinking_models import (
    LLM_JSON_FORMAT_CONSUMER_IDS,
    THINKING_MODEL_NAME_MARKERS,
    filter_models_for_json_consumers,
    is_thinking_model,
    selection_uses_thinking_for_json,
)

if TYPE_CHECKING:
    from transcriptx.core.utils.config.main import TranscriptXConfig

_DEFAULT_OLLAMA_MODEL = "qwen3:8b"
DEFAULT_OLLAMA_MODEL = _DEFAULT_OLLAMA_MODEL
_DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"


def get_llm_client(
    config: "TranscriptXConfig | None" = None,
    *,
    model: str | None = None,
) -> LLMClient:
    """
    Return the configured LLM client.

    - disabled or provider ``null`` -> ``NullLLMClient``
    - provider ``ollama`` -> ``OllamaClient``
    - enabled unsupported provider -> ``LLMConfigurationError``

    Pass ``model`` to override ``llm.model`` for this client only (run-scoped
    selection should resolve the tag before calling this factory).
    """
    if config is None:
        from transcriptx.core.utils.config import get_config

        config = get_config()

    llm = config.llm
    provider = (llm.provider or "null").strip().lower()

    if not llm.enabled or provider in ("null", ""):
        return NullLLMClient()

    if provider == "ollama":
        if model and str(model).strip():
            resolved_model = str(model).strip()
        else:
            resolved_model = llm.model or _DEFAULT_OLLAMA_MODEL
        base_url = resolve_ollama_base_url(llm.base_url or _DEFAULT_OLLAMA_BASE_URL)
        return OllamaClient(
            base_url=base_url,
            model=resolved_model,
            seed=int(llm.seed),
            request_timeout=float(llm.request_timeout),
            availability_timeout=float(llm.availability_timeout),
            max_output_tokens=llm.max_output_tokens,
        )

    raise LLMConfigurationError(f"Unsupported LLM provider: {llm.provider!r}")


__all__ = [
    "LLMClient",
    "NullLLMClient",
    "OllamaClient",
    "LLMConfigurationError",
    "LLM_CONFIGURATION_ERROR",
    "DEFAULT_OLLAMA_MODEL",
    "get_llm_client",
    "normalize_base_url",
    "resolve_ollama_base_url",
    "list_installed_ollama_models",
    "OllamaModelListResult",
    "parse_ollama_tags_payload",
    "LLM_JSON_FORMAT_CONSUMER_IDS",
    "THINKING_MODEL_NAME_MARKERS",
    "filter_models_for_json_consumers",
    "is_thinking_model",
    "selection_uses_thinking_for_json",
]
