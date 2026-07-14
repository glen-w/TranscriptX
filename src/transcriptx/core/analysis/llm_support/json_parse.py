"""Generic JSON handling for LLM responses: fence stripping and light repair.

Feature-specific schema validation lives in the feature contract modules
(``narrative_contract``, ``action_items_contract``), not here.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

__all__ = [
    "strip_json_fence",
    "loads_llm_json",
]


def strip_json_fence(text: str) -> str:
    """Strip one complete Markdown code fence if present; do not extract from prose."""
    stripped = text.strip()
    fence_match = re.match(
        r"^```(?:json)?\s*\n?(.*?)\n?```\s*$",
        stripped,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if fence_match:
        return fence_match.group(1).strip()
    return stripped


def _repair_common_llm_json_issues(text: str) -> str:
    """Apply conservative fixes for common local-LLM JSON mistakes."""
    repaired = re.sub(r",(\s*[}\]])", r"\1", text)
    repaired = re.sub(r"}\s*{", "},{", repaired)
    repaired = re.sub(r"]\s*\[", "],[", repaired)
    return repaired


def loads_llm_json(text: str) -> Any:
    """Parse JSON from an LLM response with light repair for common defects.

    Tries strict ``json.loads`` first, then trailing-comma / missing-comma
    repairs, then ``raw_decode`` of the first object (tolerates trailing junk).
    """
    candidate = strip_json_fence(text)
    attempts = (candidate, _repair_common_llm_json_issues(candidate))
    last_error: Optional[json.JSONDecodeError] = None
    for attempt in attempts:
        try:
            return json.loads(attempt)
        except json.JSONDecodeError as exc:
            last_error = exc
        start = attempt.find("{")
        if start < 0:
            continue
        try:
            data, _end = json.JSONDecoder().raw_decode(attempt, start)
            return data
        except json.JSONDecodeError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise json.JSONDecodeError("Expecting value", candidate, 0)
