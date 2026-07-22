"""Heuristics for Ollama "thinking" models that often leave ``response`` empty.

Several TranscriptX consumers request ``format=json``. Thinking-family models
(Qwen3, DeepSeek-R1, GPT-OSS, …) may put tokens in ``thinking`` while leaving
``response`` blank; the Ollama client then raises ``LLMResponseError``.
"""

from __future__ import annotations

from typing import Iterable

# Substring markers matched against the full Ollama tag (case-insensitive).
# Keep in sync with live-test diversity helpers; prefer false positives over
# letting a known-bad family into JSON-format selectors.
THINKING_MODEL_NAME_MARKERS: tuple[str, ...] = (
    "qwen3",  # includes qwen3:*, qwen3.6:*, qwen3-coder:*
    "deepseek-r1",
    "gpt-oss",
)

# LLM consumers that call ``generate(..., response_format="json")``.
LLM_JSON_FORMAT_CONSUMER_IDS: frozenset[str] = frozenset(
    {
        "narrative_summary",
        "llm_action_items",
        "chart_descriptions",
        "group_llm_synthesis",
    }
)


def is_thinking_model(name: str | None) -> bool:
    """Return True when ``name`` looks like a thinking-family Ollama tag."""
    if not isinstance(name, str):
        return False
    lowered = name.strip().lower()
    if not lowered:
        return False
    return any(marker in lowered for marker in THINKING_MODEL_NAME_MARKERS)


def filter_models_for_json_consumers(
    installed: Iterable[str],
    *,
    include_thinking: bool = False,
) -> tuple[str, ...]:
    """Return installed tags suitable for JSON-format LLM consumers."""
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
