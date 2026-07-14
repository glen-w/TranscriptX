"""Narrative-summary output contract: schema constants and strict parser."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from transcriptx.core.analysis.llm_support.json_parse import strip_json_fence
from transcriptx.core.llm.errors import LLMResponseError

__all__ = [
    "parse_narrative_json",
]

_NARRATIVE_SCHEMA_KEYS = frozenset({"narrative"})


def parse_narrative_json(
    text: str,
    *,
    max_output_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    """Parse narrative module JSON: strip one fence, parse entire remainder, validate schema."""
    candidate = strip_json_fence(text)
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise LLMResponseError(f"Narrative output is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise LLMResponseError("Narrative output JSON must be an object")
    extra_keys = set(data.keys()) - _NARRATIVE_SCHEMA_KEYS
    if extra_keys:
        raise LLMResponseError(
            f"Narrative output contains unexpected keys: {sorted(extra_keys)}"
        )
    narrative = data.get("narrative")
    if not isinstance(narrative, str) or not narrative.strip():
        raise LLMResponseError("Narrative output missing non-empty 'narrative' field")
    narrative = narrative.strip()
    if max_output_tokens is not None and max_output_tokens > 0:
        char_limit = max_output_tokens * 4
        if len(narrative) > char_limit:
            raise LLMResponseError(
                f"Narrative output exceeds expected length ({len(narrative)} > {char_limit})"
            )
    return {"narrative": narrative}
