"""Action-items feature contract: schema validation, grounding, dedupe,
ordering, and cache identity.

Rendering lives in ``action_items_render`` so export code can render without
importing parsing and grounding machinery.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from transcriptx.core.analysis.llm_support.hashing import sha256_canonical_json
from transcriptx.core.analysis.llm_support.json_parse import (
    loads_llm_json,
    strip_json_fence,
)
from transcriptx.core.llm.errors import LLMResponseError

__all__ = [
    "parse_action_items_json",
    "ground_action_items",
    "dedupe_action_items",
    "order_action_items",
    "build_llm_action_items_cache_key",
]

_ACTION_ITEMS_SCHEMA_KEYS = frozenset({"items"})
_ACTION_ITEM_KEYS = frozenset(
    {"text", "owner", "deadline", "status", "quote", "confidence"}
)
_VALID_ACTION_STATUSES = frozenset({"open", "done", "unclear"})


def _normalise_whitespace(text: str) -> str:
    return " ".join(text.split())


def _validate_confidence(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LLMResponseError("Action item confidence must be a number")
    confidence = float(value)
    if not (
        confidence == confidence
        and confidence != float("inf")
        and confidence != float("-inf")
    ):
        raise LLMResponseError("Action item confidence must be finite")
    if confidence < 0.0 or confidence > 1.0:
        raise LLMResponseError("Action item confidence must be in [0, 1]")
    return confidence


def _validate_action_item(raw: Any, *, index: int) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise LLMResponseError(f"Action item at index {index} must be an object")
    extra = set(raw.keys()) - _ACTION_ITEM_KEYS
    if extra:
        raise LLMResponseError(
            f"Action item at index {index} contains unexpected keys: {sorted(extra)}"
        )
    text = raw.get("text")
    if not isinstance(text, str) or not text.strip():
        raise LLMResponseError(
            f"Action item at index {index} missing non-empty 'text' field"
        )
    owner = raw.get("owner")
    if owner is not None:
        if not isinstance(owner, str):
            raise LLMResponseError(
                f"Action item at index {index} owner must be string or null"
            )
        owner = owner.strip() or None
    deadline = raw.get("deadline")
    if deadline is not None:
        if not isinstance(deadline, str):
            raise LLMResponseError(
                f"Action item at index {index} deadline must be string or null"
            )
        deadline = deadline.strip() or None
    status = raw.get("status")
    if status not in _VALID_ACTION_STATUSES:
        raise LLMResponseError(
            f"Action item at index {index} status must be one of: open, done, unclear"
        )
    quote = raw.get("quote")
    if quote is not None:
        if not isinstance(quote, str):
            raise LLMResponseError(
                f"Action item at index {index} quote must be string or null"
            )
        quote = quote.strip() or None
    confidence = _validate_confidence(raw.get("confidence"))
    return {
        "text": text.strip(),
        "owner": owner,
        "deadline": deadline,
        "status": status,
        "quote": quote,
        "confidence": confidence,
    }


def parse_action_items_json(
    text: str,
    *,
    max_output_tokens: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Parse action-items JSON: strip one fence, lightly repair, validate schema."""
    candidate = strip_json_fence(text)
    try:
        data = loads_llm_json(text)
    except json.JSONDecodeError as exc:
        raise LLMResponseError(f"Action items output is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise LLMResponseError("Action items output JSON must be an object")
    extra_keys = set(data.keys()) - _ACTION_ITEMS_SCHEMA_KEYS
    if extra_keys:
        raise LLMResponseError(
            f"Action items output contains unexpected keys: {sorted(extra_keys)}"
        )
    items_raw = data.get("items")
    if not isinstance(items_raw, list):
        raise LLMResponseError("Action items output missing 'items' array")
    if max_output_tokens is not None and max_output_tokens > 0:
        char_limit = max_output_tokens * 4
        if len(candidate) > char_limit:
            raise LLMResponseError(
                f"Action items output exceeds expected length ({len(candidate)} > {char_limit})"
            )
    return [_validate_action_item(item, index=i) for i, item in enumerate(items_raw)]


def _substring_offset(haystack: str, needle: str) -> Optional[int]:
    if not needle:
        return None
    idx = haystack.find(needle)
    return idx if idx >= 0 else None


def ground_action_items(
    items: List[Dict[str, Any]],
    bounded_transcript: str,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Ground quotes and text against the bounded transcript block."""
    normalised_transcript = _normalise_whitespace(bounded_transcript)
    grounded: List[Dict[str, Any]] = []
    diagnostics = {
        "items_parsed": len(items),
        "items_grounded": 0,
        "items_dropped": 0,
        "quotes_nulled": 0,
    }
    for item in items:
        entry = dict(item)
        text_norm = _normalise_whitespace(entry["text"])
        text_grounded = _substring_offset(normalised_transcript, text_norm) is not None
        quote_original = entry.get("quote")
        quote_grounded = False
        if quote_original:
            quote_norm = _normalise_whitespace(quote_original)
            quote_grounded = (
                _substring_offset(normalised_transcript, quote_norm) is not None
            )
            if not quote_grounded:
                entry["quote"] = None
                entry["confidence"] = max(0.0, float(entry["confidence"]) * 0.5)
                diagnostics["quotes_nulled"] += 1
        if not text_grounded and not quote_grounded:
            diagnostics["items_dropped"] += 1
            continue
        diagnostics["items_grounded"] += 1
        grounded.append(entry)
    return grounded, diagnostics


def _dedupe_key(item: Dict[str, Any]) -> Tuple[str, str, str, str]:
    return (
        item["text"].strip().lower(),
        (item.get("owner") or "").strip().lower(),
        (item.get("deadline") or "").strip().lower(),
        item["status"],
    )


def dedupe_action_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep strongest grounded item per normalised key."""
    best: Dict[Tuple[str, str, str, str], Tuple[int, Dict[str, Any]]] = {}
    for index, item in enumerate(items):
        key = _dedupe_key(item)
        score = (
            1 if item.get("quote") else 0,
            float(item.get("confidence", 0.0)),
            -index,
        )
        existing = best.get(key)
        if existing is None or score > (
            1 if existing[1].get("quote") else 0,
            float(existing[1].get("confidence", 0.0)),
            -existing[0],
        ):
            best[key] = (index, dict(item))
    return [pair[1] for pair in sorted(best.values(), key=lambda p: p[0])]


def order_action_items(
    items: List[Dict[str, Any]],
    bounded_transcript: str,
) -> List[Dict[str, Any]]:
    """Order by transcript occurrence (quote, then text), fallback to model order."""
    normalised_transcript = _normalise_whitespace(bounded_transcript)

    def sort_key(item: Dict[str, Any]) -> Tuple[int, int]:
        model_index = int(item.get("_model_index", 0))
        quote = item.get("quote")
        if quote:
            offset = _substring_offset(
                normalised_transcript, _normalise_whitespace(quote)
            )
            if offset is not None:
                return (offset, model_index)
        text_offset = _substring_offset(
            normalised_transcript, _normalise_whitespace(item["text"])
        )
        if text_offset is not None:
            return (text_offset, model_index)
        return (10**9, model_index)

    ordered = sorted(items, key=sort_key)
    cleaned: List[Dict[str, Any]] = []
    for item in ordered:
        entry = {k: v for k, v in item.items() if k != "_model_index"}
        cleaned.append(entry)
    return cleaned


def build_llm_action_items_cache_key(
    *,
    module_version: str,
    prompt_version: str,
    schema_id: str,
    transcript_fingerprint: str,
    bounded_input_fingerprint: str,
    model: str,
    runtime: Dict[str, Any],
    generation_options: Dict[str, Any],
    llm_request_sha256: str,
) -> str:
    payload = {
        "module": "llm_action_items",
        "module_version": module_version,
        "prompt_version": prompt_version,
        "schema_id": schema_id,
        "transcript_fingerprint": transcript_fingerprint,
        "bounded_input_fingerprint": bounded_input_fingerprint,
        "model": model,
        "runtime": runtime,
        "generation_options": generation_options,
        "llm_request_sha256": llm_request_sha256,
    }
    return sha256_canonical_json(payload)
