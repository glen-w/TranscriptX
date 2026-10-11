"""Heuristics and capability profiles for Ollama "thinking" models.

Several TranscriptX consumers request ``format=json``. Thinking-family models
(Qwen3, DeepSeek-R1, GPT-OSS, …) may put tokens in ``thinking`` while leaving
``response`` blank unless ``think: false`` is sent. Prefer live ``/api/show``
metadata when available; fall back to name markers when offline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

# Substring markers matched against the full Ollama tag (case-insensitive).
# Offline / show-unavailable fallback only; prefer resolve_thinking_profile.
THINKING_MODEL_NAME_MARKERS: tuple[str, ...] = (
    "qwen3",  # qwen3:*, qwen3.6:*, qwen3.8:*, qwen3-coder:*, qwen3-vl:*
    "deepseek-r1",
    "gpt-oss",
)

# LLM consumers that call ``generate(..., response_format="json")``.
LLM_JSON_FORMAT_CONSUMER_IDS: frozenset[str] = frozenset(
    {
        "narrative_summary",
        "llm_action_items",
        "llm_custom_qa",
        "chart_descriptions",
        "group_llm_synthesis",
        "speaker_name_suggestions",
        "rename_suggestions",
        "corrections_studio",
        "topic_shift",
    }
)

ThinkingSource = Literal["show", "name", "unknown"]


@dataclass(frozen=True)
class ThinkingProfile:
    """Resolved thinking behavior for one Ollama tag."""

    model: str
    is_thinking: bool
    can_disable: bool
    source: ThinkingSource


def is_thinking_model(name: str | None) -> bool:
    """Return True when ``name`` looks like a thinking-family Ollama tag."""
    if not isinstance(name, str):
        return False
    lowered = name.strip().lower()
    if not lowered:
        return False
    return any(marker in lowered for marker in THINKING_MODEL_NAME_MARKERS)


def resolve_thinking_profile(
    model: str | None,
    *,
    base_url: str | None = None,
    timeout: float = 5.0,
    prefer_show: bool = True,
) -> ThinkingProfile:
    """Resolve thinking profile from ``/api/show`` when possible, else name heuristics.

    Runtime JSON gating and ``think: false`` decisions should use this helper.
    ``is_thinking_model`` remains the offline name-only check.
    """
    tag = (model or "").strip()
    if not tag:
        return ThinkingProfile(
            model="", is_thinking=False, can_disable=False, source="unknown"
        )

    if prefer_show:
        try:
            from transcriptx.core.llm.ollama_capabilities import (
                thinking_controls_for_model,
            )

            controls = thinking_controls_for_model(
                tag, base_url=base_url, timeout=timeout
            )
            if controls.reports_thinking_capability or controls.has_thinking_object:
                return ThinkingProfile(
                    model=tag,
                    is_thinking=True,
                    can_disable=controls.can_disable_thinking,
                    source="show",
                )
            # Successful show with no thinking metadata: trust non-thinking unless
            # the name heuristic still flags a known-bad family (stale template).
            if is_thinking_model(tag):
                return ThinkingProfile(
                    model=tag,
                    is_thinking=True,
                    can_disable=False,
                    source="name",
                )
            return ThinkingProfile(
                model=tag,
                is_thinking=False,
                can_disable=False,
                source="show",
            )
        except Exception:
            pass

    if is_thinking_model(tag):
        return ThinkingProfile(
            model=tag, is_thinking=True, can_disable=False, source="name"
        )
    return ThinkingProfile(
        model=tag, is_thinking=False, can_disable=False, source="unknown"
    )


def filter_models_for_json_consumers(
    installed: Iterable[str],
    *,
    include_thinking: bool = False,
) -> tuple[str, ...]:
    """Return installed tags suitable for JSON-format LLM consumers.

    Name-heuristic filter for UI option lists when show metadata is not yet
    loaded. Prefer richer gating via ``resolve_thinking_profile`` + secondary.
    """
    out: list[str] = []
    for name in installed:
        if not isinstance(name, str) or not name.strip():
            continue
        if include_thinking or not is_thinking_model(name):
            out.append(name)
    return tuple(out)


def selection_uses_thinking_for_json(
    *,
    mode: str,
    shared_model: str | None,
    module_models: dict[str, str] | None,
    json_consumer_ids: Iterable[str],
) -> list[str]:
    """Return JSON consumer ids assigned a thinking model (human-facing)."""
    flagged: list[str] = []
    modules = module_models or {}
    for consumer_id in json_consumer_ids:
        if mode == "shared":
            model = shared_model
        else:
            model = modules.get(consumer_id) or shared_model
        if is_thinking_model(model):
            flagged.append(consumer_id)
    return flagged


def json_thinking_needs_secondary(
    *,
    preferred_model: str | None,
    fallback_model: str | None,
    base_url: str | None = None,
) -> bool:
    """True when preferred is thinking and cannot disable without a secondary."""
    profile = resolve_thinking_profile(preferred_model, base_url=base_url)
    if not profile.is_thinking:
        return False
    if profile.can_disable:
        return False
    secondary = (fallback_model or "").strip()
    if not secondary or secondary == (preferred_model or "").strip():
        return True
    return False
