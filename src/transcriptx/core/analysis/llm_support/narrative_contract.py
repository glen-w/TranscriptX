"""Narrative-summary output contract: schema constants and strict parser."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from transcriptx.core.analysis.llm_support.json_parse import (
    loads_llm_json_document,
    strip_json_fence,
)
from transcriptx.core.llm.errors import LLMResponseError

__all__ = [
    "parse_narrative_json",
]

_NARRATIVE_SCHEMA_KEYS = frozenset({"narrative"})
_JSON_STRING_ESCAPES = {
    "n": "\n",
    "r": "\r",
    "t": "\t",
    '"': '"',
    "\\": "\\",
    "/": "/",
}


def _decode_loose_json_string(raw: str) -> str:
    """Decode a JSON string body that may contain unescaped quotes or newlines."""
    out: list[str] = []
    i = 0
    length = len(raw)
    while i < length:
        ch = raw[i]
        if ch == "\\" and i + 1 < length:
            nxt = raw[i + 1]
            if nxt in _JSON_STRING_ESCAPES:
                out.append(_JSON_STRING_ESCAPES[nxt])
                i += 2
                continue
            if nxt == "u" and i + 5 < length:
                hex_part = raw[i + 2 : i + 6]
                try:
                    out.append(chr(int(hex_part, 16)))
                    i += 6
                    continue
                except ValueError:
                    pass
        out.append(ch)
        i += 1
    return "".join(out)


def _recover_narrative_object(candidate: str) -> Optional[Dict[str, str]]:
    """Recover ``{"narrative": "..."}`` when the string body has unescaped quotes.

    Local models often emit executive prose with literal ``"`` inside the
    narrative value, which yields ``Expecting ',' delimiter`` from ``json.loads``.
    For this single-string schema we take content from the opening quote after
    ``"narrative":`` through the last quote before the final ``}``.
    """
    stripped = candidate.strip()
    if not (stripped.startswith("{") and stripped.endswith("}")):
        return None
    key_match = re.search(r'"narrative"\s*:', stripped)
    if key_match is None:
        return None
    open_quote = key_match.end()
    while open_quote < len(stripped) and stripped[open_quote] in " \t\r\n":
        open_quote += 1
    if open_quote >= len(stripped) or stripped[open_quote] != '"':
        return None
    close_quote = len(stripped) - 2
    while close_quote > open_quote and stripped[close_quote] in " \t\r\n":
        close_quote -= 1
    if close_quote <= open_quote or stripped[close_quote] != '"':
        return None
    narrative = _decode_loose_json_string(stripped[open_quote + 1 : close_quote])
    if not narrative.strip():
        return None
    return {"narrative": narrative}


def parse_narrative_json(
    text: str,
    *,
    max_output_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    """Parse narrative module JSON: strip one fence, parse document, validate schema."""
    try:
        data = loads_llm_json_document(text)
    except json.JSONDecodeError as exc:
        recovered = _recover_narrative_object(strip_json_fence(text))
        if recovered is None:
            raise LLMResponseError(
                f"Narrative output is not valid JSON: {exc}"
            ) from exc
        data = recovered
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
