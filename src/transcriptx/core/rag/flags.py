"""Env helpers for the Ask / RAG feature flag."""

from __future__ import annotations

import os

_TRUTHY = frozenset({"1", "true", "yes", "on"})
_DEFAULT_OLLAMA = "http://localhost:11434"


def parse_rag_enabled(raw: str | None) -> bool:
    """True only for 1/true/yes/on (case-insensitive). Empty and other values are off."""
    if raw is None:
        return False
    return raw.strip().lower() in _TRUTHY


def rag_enabled_from_env() -> bool:
    return parse_rag_enabled(os.environ.get("TRANSCRIPTX_RAG_ENABLED"))


def ollama_base_url_from_env() -> str:
    """Embed server URL: Ollama override, else LLM base URL, else localhost."""
    for key in ("TRANSCRIPTX_OLLAMA_BASE_URL", "TRANSCRIPTX_LLM_BASE_URL"):
        value = os.environ.get(key)
        if value and value.strip():
            return value.strip()
    return _DEFAULT_OLLAMA
