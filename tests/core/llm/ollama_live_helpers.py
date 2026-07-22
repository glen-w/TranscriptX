"""Shared helpers for gated live Ollama tests."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Iterable, Sequence

from transcriptx.core.llm import DEFAULT_OLLAMA_MODEL
from transcriptx.core.llm.thinking_models import is_thinking_model as _is_thinking_model

# Family/size buckets used by the diversity selector. Order within each bucket
# prefers faster/smaller tags first.
_BUCKET_CANDIDATES: dict[str, tuple[str, ...]] = {
    "small_instruct": (
        "llama3.2:3b",
        "gemma3:1b",
        "qwen3:4b",
    ),
    "mid_instruct": (
        "gemma3:12b",
        "qwen2.5:7b",
        "mistral:latest",
        "qwen3:8b",
    ),
    "large_instruct": (
        "qwen3.6:27b",
        "gpt-oss:20b",
        "qwen3-coder:30b",
    ),
    "thinking": (
        "qwen3:8b",
        "qwen3:4b",
        "qwen3.6:27b",
        "deepseek-r1:8b",
        "gpt-oss:20b",
    ),
}


@dataclass(frozen=True)
class SelectedModel:
    name: str
    bucket: str
    thinking: bool


def live_base_url() -> str:
    """Resolve Ollama URL for host-side live tests.

    Prefers ``TRANSCRIPTX_LLM_LIVE_BASE_URL``. Ignores a project ``.env`` value of
    ``host.docker.internal`` (meant for in-container GUI → host Ollama) so live
    tests run correctly on the Mac host.
    """
    explicit = os.getenv("TRANSCRIPTX_LLM_LIVE_BASE_URL", "").strip()
    if explicit:
        return explicit
    configured = os.getenv("TRANSCRIPTX_LLM_BASE_URL", "").strip()
    if configured and (
        "127.0.0.1" in configured or "localhost" in configured.split("://", 1)[-1]
    ):
        return configured
    return "http://127.0.0.1:11434"


def installed_ollama_models(base_url: str) -> list[str]:
    from transcriptx.core.llm.ollama_client import list_installed_ollama_models

    result = list_installed_ollama_models(base_url)
    if result.error:
        raise AssertionError(result.error)
    return list(result.models)


def is_thinking_model(name: str) -> bool:
    """Proxy to production heuristic (kept for live-test imports)."""
    return _is_thinking_model(name)


def resolve_live_model(base_url: str) -> str:
    """Pick a single default model for legacy single-model live tests."""
    env_model = os.getenv("TRANSCRIPTX_LLM_MODEL", "").strip()
    if env_model:
        return env_model
    installed = installed_ollama_models(base_url)
    preferred = (
        "qwen3:4b",
        "llama3.2:3b",
        DEFAULT_OLLAMA_MODEL,
        "qwen3:8b",
        "qwen2.5:7b",
    )
    for name in preferred:
        if name in installed:
            return name
    if installed:
        return installed[0]
    return DEFAULT_OLLAMA_MODEL


def _first_installed(candidates: Sequence[str], installed: set[str]) -> str | None:
    for name in candidates:
        if name in installed:
            return name
    return None


def select_diverse_models(
    installed: Iterable[str],
    *,
    max_models: int = 4,
    force: Sequence[str] | None = None,
) -> list[SelectedModel]:
    """Pick at most one model per diversity bucket from installed tags.

    ``TRANSCRIPTX_LLM_LIVE_MODELS`` (comma-separated) or ``force`` overrides the
    automatic selection entirely.
    """
    installed_list = list(installed)
    installed_set = set(installed_list)

    forced_env = os.getenv("TRANSCRIPTX_LLM_LIVE_MODELS", "").strip()
    forced = list(force) if force is not None else []
    if not forced and forced_env:
        forced = [part.strip() for part in forced_env.split(",") if part.strip()]
    if forced:
        missing = [name for name in forced if name not in installed_set]
        if missing:
            raise AssertionError(
                f"Forced live models not installed: {missing}; have {sorted(installed_set)}"
            )
        return [
            SelectedModel(name=name, bucket="forced", thinking=is_thinking_model(name))
            for name in forced
        ]

    selected: list[SelectedModel] = []
    seen: set[str] = set()

    # Prefer gemma3:12b for the mid bucket when present (production JSON regression).
    for bucket, candidates in _BUCKET_CANDIDATES.items():
        ordered = candidates
        if bucket == "mid_instruct" and "gemma3:12b" in installed_set:
            ordered = ("gemma3:12b",) + tuple(
                c for c in candidates if c != "gemma3:12b"
            )
        name = _first_installed(ordered, installed_set)
        if name is None or name in seen:
            continue
        selected.append(
            SelectedModel(
                name=name,
                bucket=bucket,
                thinking=bucket == "thinking" or is_thinking_model(name),
            )
        )
        seen.add(name)
        if len(selected) >= max_models:
            break

    return selected
