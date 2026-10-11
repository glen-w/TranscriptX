"""Parse Ollama ``/api/show`` thinking capability metadata.

Authoritative when show succeeds; callers should fall back to name heuristics
when the payload is missing or incomplete (stale templates, offline).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Mapping

from transcriptx.core.llm.ollama_client import show_ollama_model

_SHOW_TTL_SECONDS = 120.0
_lock = threading.Lock()
_cache: dict[tuple[str, str], tuple[float, dict[str, Any] | None]] = {}


@dataclass(frozen=True)
class OllamaThinkingControls:
    """Thinking-related fields from an Ollama ``/api/show`` payload."""

    capabilities: frozenset[str]
    values: tuple[object, ...]
    default: object | None
    has_thinking_object: bool

    @property
    def reports_thinking_capability(self) -> bool:
        return "thinking" in self.capabilities

    @property
    def can_disable_thinking(self) -> bool:
        return False in self.values or any(
            isinstance(v, str) and v.strip().lower() == "false" for v in self.values
        )


def parse_thinking_controls(show_payload: Mapping[str, Any] | None) -> OllamaThinkingControls:
    """Extract thinking controls from a show payload (never raises)."""
    if not isinstance(show_payload, Mapping):
        return OllamaThinkingControls(
            capabilities=frozenset(),
            values=(),
            default=None,
            has_thinking_object=False,
        )
    caps_raw = show_payload.get("capabilities")
    caps: set[str] = set()
    if isinstance(caps_raw, list):
        for item in caps_raw:
            if isinstance(item, str) and item.strip():
                caps.add(item.strip().lower())
    thinking = show_payload.get("thinking")
    if not isinstance(thinking, Mapping):
        return OllamaThinkingControls(
            capabilities=frozenset(caps),
            values=(),
            default=None,
            has_thinking_object=False,
        )
    values_raw = thinking.get("values")
    values: list[object] = []
    if isinstance(values_raw, list):
        for item in values_raw:
            if isinstance(item, bool):
                values.append(item)
            elif isinstance(item, str) and item.strip():
                values.append(item.strip())
            elif isinstance(item, (int, float)) and not isinstance(item, bool):
                # Ollama docs: numbers are not supported for think levels; keep raw
                # for can_disable checks only if somehow present as 0.
                values.append(item)
    default = thinking.get("default", None)
    return OllamaThinkingControls(
        capabilities=frozenset(caps),
        values=tuple(values),
        default=default,
        has_thinking_object=True,
    )


def cached_show_ollama_model(
    model: str,
    base_url: str | None = None,
    *,
    timeout: float = 5.0,
    ttl_seconds: float = _SHOW_TTL_SECONDS,
) -> dict[str, Any] | None:
    """Process-wide TTL cache around ``show_ollama_model``."""
    tag = (model or "").strip()
    if not tag:
        return None
    key = ((base_url or "").strip(), tag)
    now = time.monotonic()
    with _lock:
        hit = _cache.get(key)
        if hit is not None and (now - hit[0]) < ttl_seconds:
            return hit[1]
    payload = show_ollama_model(tag, base_url=base_url, timeout=timeout)
    with _lock:
        _cache[key] = (now, payload)
    return payload


def clear_show_cache() -> None:
    """Test helper: drop cached show payloads."""
    with _lock:
        _cache.clear()


def thinking_controls_for_model(
    model: str,
    *,
    base_url: str | None = None,
    timeout: float = 5.0,
) -> OllamaThinkingControls:
    """Show-based thinking controls for one installed tag."""
    return parse_thinking_controls(
        cached_show_ollama_model(model, base_url=base_url, timeout=timeout)
    )
