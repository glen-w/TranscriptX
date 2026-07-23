"""Meeting-extract feature contract (llm_action_items v2).

Schema validation, grounding, dedupe, ordering, bounds, v1 coerce, and cache
identity. Rendering lives in ``action_items_render``.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from transcriptx.core.analysis.llm_support.hashing import sha256_canonical_json
from transcriptx.core.analysis.llm_support.json_parse import (
    loads_llm_json,
    strip_json_fence,
)
from transcriptx.core.llm.errors import LLMResponseError

__all__ = [
    "LLM_ACTION_ITEMS_SCHEMA_ID",
    "LLM_ACTION_ITEMS_SCHEMA_ID_V1",
    "LLM_ACTION_ITEMS_RENDER_CONTRACT_ID",
    "LLM_ACTION_ITEMS_GROUP_SCHEMA_VERSION",
    "RECORD_TYPES",
    "RECORD_TYPE_ORDER",
    "RECORD_TYPE_LABELS",
    "STATUSES",
    "TYPES_REQUIRING_DONE_EVIDENCE",
    "DONE_EVIDENCE_LEXICON",
    "MAX_ITEMS_TOTAL",
    "MAX_ITEMS_PER_TYPE",
    "HUMAN_REVIEW_BANNER",
    "EMPTY_EXTRACTS_MESSAGE",
    "TITLE_MEETING_EXTRACTS",
    "empty_counts_by_type",
    "empty_diagnostics",
    "parse_action_items_json",
    "ground_action_items",
    "dedupe_action_items",
    "truncate_action_items",
    "order_action_items",
    "finalize_action_items",
    "build_counts_by_type",
    "is_v1_action_items_payload",
    "coerce_v1_action_items_payload",
    "build_llm_action_items_cache_key",
]

LLM_ACTION_ITEMS_SCHEMA_ID = "transcriptx.llm_action_items.v2"
LLM_ACTION_ITEMS_SCHEMA_ID_V1 = "transcriptx.llm_action_items.v1"
LLM_ACTION_ITEMS_RENDER_CONTRACT_ID = "transcriptx.llm_action_items.render.v2"
LLM_ACTION_ITEMS_GROUP_SCHEMA_VERSION = 2

RECORD_TYPES = (
    "decision",
    "commitment",
    "action_item",
    "proposal",
    "open_question",
)
RECORD_TYPE_ORDER = RECORD_TYPES
RECORD_TYPE_LABELS = {
    "decision": "Decisions",
    "commitment": "Commitments",
    "action_item": "Action items",
    "proposal": "Proposals",
    "open_question": "Open questions",
}
STATUSES = ("open", "done", "unclear")
TYPES_REQUIRING_DONE_EVIDENCE = frozenset({"decision", "proposal", "open_question"})
DONE_EVIDENCE_LEXICON = frozenset(
    {
        "done",
        "completed",
        "resolved",
        "superseded",
        "withdrawn",
        "answered",
        "closed",
        "cancelled",
        "canceled",
        "retracted",
    }
)
MAX_ITEMS_TOTAL = 48
MAX_ITEMS_PER_TYPE = 16

HUMAN_REVIEW_BANNER = "AI-generated draft. Human review required."
EMPTY_EXTRACTS_MESSAGE = "No meeting extracts found."
TITLE_MEETING_EXTRACTS = "Meeting extracts"

_ACTION_ITEMS_SCHEMA_KEYS = frozenset({"items"})
_ACTION_ITEM_KEYS = frozenset(
    {"record_type", "text", "owner", "deadline", "status", "quote", "confidence"}
)
_VALID_RECORD_TYPES = frozenset(RECORD_TYPES)
_VALID_ACTION_STATUSES = frozenset(STATUSES)
_RECORD_TYPE_RANK = {name: index for index, name in enumerate(RECORD_TYPE_ORDER)}
_DONE_EVIDENCE_RE = re.compile(
    r"\b(?:"
    + "|".join(re.escape(word) for word in sorted(DONE_EVIDENCE_LEXICON))
    + r")\b",
    re.IGNORECASE,
)


def empty_counts_by_type() -> Dict[str, int]:
    return {record_type: 0 for record_type in RECORD_TYPES}


def empty_diagnostics() -> Dict[str, Any]:
    return {
        "items_raw": 0,
        "items_parsed_valid": 0,
        "record_type_defaulted": 0,
        "items_invalid_dropped": 0,
        "status_unsupported_dropped": 0,
        "items_ungrounded_dropped": 0,
        "quotes_nulled": 0,
        "items_duplicate_removed": 0,
        "items_truncated": 0,
        "output_truncated": 0,
        "counts_by_type": empty_counts_by_type(),
        "items_committed": 0,
    }


def build_counts_by_type(items: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = empty_counts_by_type()
    for item in items:
        record_type = item.get("record_type")
        if record_type in counts:
            counts[str(record_type)] += 1
    return counts


def _normalise_whitespace(text: str) -> str:
    return " ".join(text.split())


def _validate_confidence(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    confidence = float(value)
    if not (
        confidence == confidence
        and confidence != float("inf")
        and confidence != float("-inf")
    ):
        return None
    if confidence < 0.0 or confidence > 1.0:
        return None
    return confidence


def _optional_string_field(
    value: Any,
    *,
    coerce_scalars: bool,
) -> Optional[str]:
    """Normalise optional string fields from common LLM shape mistakes."""
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if not coerce_scalars:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        parts: List[str] = []
        for part in value:
            if isinstance(part, str):
                cleaned = part.strip()
                if cleaned:
                    parts.append(cleaned)
            elif isinstance(part, bool):
                continue
            elif isinstance(part, (int, float)):
                parts.append(str(part))
            else:
                return None
        return ", ".join(parts) or None
    return None


def _has_done_evidence(text: str, quote: Optional[str]) -> bool:
    haystacks = [text]
    if quote:
        haystacks.append(quote)
    for haystack in haystacks:
        if _DONE_EVIDENCE_RE.search(_normalise_whitespace(haystack)):
            return True
    return False


def _validate_action_item(
    raw: Any,
    *,
    index: int,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Return (item, drop_reason) where drop_reason is diagnostic bucket or None."""
    if not isinstance(raw, dict):
        return None, "items_invalid_dropped"
    extra = set(raw.keys()) - _ACTION_ITEM_KEYS
    if extra:
        return None, "items_invalid_dropped"

    record_type_raw = raw.get("record_type", None)
    record_type_defaulted = False
    if record_type_raw is None:
        record_type = "action_item"
        record_type_defaulted = True
    elif not isinstance(record_type_raw, str):
        return None, "items_invalid_dropped"
    else:
        candidate = record_type_raw.strip()
        if not candidate:
            record_type = "action_item"
            record_type_defaulted = True
        elif candidate not in _VALID_RECORD_TYPES:
            return None, "items_invalid_dropped"
        else:
            record_type = candidate

    text = raw.get("text")
    if not isinstance(text, str) or not text.strip():
        return None, "items_invalid_dropped"

    owner = _optional_string_field(raw.get("owner"), coerce_scalars=True)
    deadline = _optional_string_field(raw.get("deadline"), coerce_scalars=True)
    status = raw.get("status")
    if status not in _VALID_ACTION_STATUSES:
        return None, "status_unsupported_dropped"
    quote = _optional_string_field(raw.get("quote"), coerce_scalars=False)
    confidence = _validate_confidence(raw.get("confidence"))
    if confidence is None:
        return None, "items_invalid_dropped"

    if (
        status == "done"
        and record_type in TYPES_REQUIRING_DONE_EVIDENCE
        and not _has_done_evidence(text, quote)
    ):
        return None, "status_unsupported_dropped"

    item = {
        "record_type": record_type,
        "text": text.strip(),
        "owner": owner,
        "deadline": deadline,
        "status": status,
        "quote": quote,
        "confidence": confidence,
        "_model_index": index,
        "_record_type_defaulted": record_type_defaulted,
    }
    return item, None


def parse_action_items_json(
    text: str,
    *,
    max_output_tokens: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Parse meeting-extract JSON with per-record isolation.

    Top-level failures raise ``LLMResponseError``. Invalid items are dropped
    and counted in diagnostics.
    """
    diagnostics = empty_diagnostics()
    candidate = strip_json_fence(text)
    if max_output_tokens is not None and max_output_tokens > 0:
        char_limit = max_output_tokens * 4
        if len(candidate) > char_limit:
            diagnostics["output_truncated"] = 1
            raise LLMResponseError(
                f"Action items output exceeds expected length ({len(candidate)} > {char_limit})"
            )
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

    diagnostics["items_raw"] = len(items_raw)
    parsed: List[Dict[str, Any]] = []
    for index, raw_item in enumerate(items_raw):
        item, drop_reason = _validate_action_item(raw_item, index=index)
        if item is None:
            assert drop_reason is not None
            diagnostics[drop_reason] = int(diagnostics.get(drop_reason, 0)) + 1
            continue
        if item.pop("_record_type_defaulted", False):
            diagnostics["record_type_defaulted"] += 1
        parsed.append(item)

    diagnostics["items_parsed_valid"] = len(parsed)
    return parsed, diagnostics


def _substring_offset(haystack: str, needle: str) -> Optional[int]:
    if not needle:
        return None
    idx = haystack.find(needle)
    return idx if idx >= 0 else None


def ground_action_items(
    items: List[Dict[str, Any]],
    bounded_transcript: str,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Ground quotes and text against the bounded transcript block.

    Record-type agnostic. Never rewrites record_type, text, owner, deadline,
    or status. May null ungrounded quotes and scale confidence.
    """
    normalised_transcript = _normalise_whitespace(bounded_transcript)
    grounded: List[Dict[str, Any]] = []
    quotes_nulled = 0
    ungrounded_dropped = 0
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
                quotes_nulled += 1
        if not text_grounded and not quote_grounded:
            ungrounded_dropped += 1
            continue
        entry["_grounded"] = True
        grounded.append(entry)
    return grounded, {
        "items_ungrounded_dropped": ungrounded_dropped,
        "quotes_nulled": quotes_nulled,
    }


def _dedupe_key(item: Dict[str, Any]) -> Tuple[str, str, str, str, str]:
    return (
        str(item.get("record_type") or "action_item"),
        item["text"].strip().lower(),
        (item.get("owner") or "").strip().lower(),
        (item.get("deadline") or "").strip().lower(),
        str(item.get("status") or ""),
    )


def _dedupe_rank(item: Dict[str, Any]) -> Tuple[int, float, int, int, str]:
    """Higher tuple wins (grounded, confidence, quote, earlier index via negation)."""
    model_index = int(item.get("_model_index", 10**9))
    return (
        1 if item.get("_grounded") else 0,
        float(item.get("confidence", 0.0)),
        1 if item.get("quote") else 0,
        -model_index,
        str(item.get("text") or "").lower(),
    )


def dedupe_action_items(
    items: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int]:
    """Keep strongest item per normalised key. Returns (items, removed_count)."""
    best: Dict[Tuple[str, str, str, str, str], Dict[str, Any]] = {}
    for item in items:
        key = _dedupe_key(item)
        existing = best.get(key)
        if existing is None or _dedupe_rank(item) > _dedupe_rank(existing):
            best[key] = dict(item)
    winners = list(best.values())
    removed = max(0, len(items) - len(winners))
    # Preserve earliest surviving model order among winners for stable iteration.
    winners.sort(key=lambda item: int(item.get("_model_index", 0)))
    return winners, removed


def truncate_action_items(
    items: List[Dict[str, Any]],
    *,
    max_total: int = MAX_ITEMS_TOTAL,
    max_per_type: int = MAX_ITEMS_PER_TYPE,
) -> Tuple[List[Dict[str, Any]], int]:
    """Keep earliest ``_model_index`` within type order; return (kept, truncated)."""
    by_type: Dict[str, List[Dict[str, Any]]] = {name: [] for name in RECORD_TYPE_ORDER}
    unknown: List[Dict[str, Any]] = []
    ordered_input = sorted(items, key=lambda item: int(item.get("_model_index", 0)))
    for item in ordered_input:
        record_type = str(item.get("record_type") or "")
        if record_type in by_type:
            by_type[record_type].append(item)
        else:
            unknown.append(item)

    kept: List[Dict[str, Any]] = []
    for record_type in RECORD_TYPE_ORDER:
        kept.extend(by_type[record_type][:max_per_type])
    kept.extend(unknown[:max_per_type])
    kept.sort(
        key=lambda item: (
            _RECORD_TYPE_RANK.get(str(item.get("record_type")), 99),
            int(item.get("_model_index", 0)),
        )
    )
    if len(kept) > max_total:
        kept = kept[:max_total]
    truncated = max(0, len(items) - len(kept))
    return kept, truncated


def order_action_items(
    items: List[Dict[str, Any]],
    bounded_transcript: str,
) -> List[Dict[str, Any]]:
    """Order by type, transcript offset, model index, text; strip internals."""
    normalised_transcript = _normalise_whitespace(bounded_transcript)

    def sort_key(item: Dict[str, Any]) -> Tuple[int, int, int, str]:
        model_index = int(item.get("_model_index", 0))
        type_rank = _RECORD_TYPE_RANK.get(str(item.get("record_type")), 99)
        quote = item.get("quote")
        offset = 10**9
        if quote:
            found = _substring_offset(
                normalised_transcript, _normalise_whitespace(quote)
            )
            if found is not None:
                offset = found
        if offset == 10**9:
            text_offset = _substring_offset(
                normalised_transcript, _normalise_whitespace(item["text"])
            )
            if text_offset is not None:
                offset = text_offset
        return (type_rank, offset, model_index, str(item.get("text") or "").lower())

    ordered = sorted(items, key=sort_key)
    cleaned: List[Dict[str, Any]] = []
    for item in ordered:
        entry = {
            k: v
            for k, v in item.items()
            if k not in {"_model_index", "_grounded", "_record_type_defaulted"}
        }
        cleaned.append(entry)
    return cleaned


def finalize_action_items(
    raw_json: str,
    bounded_transcript: str,
    *,
    max_output_tokens: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Full pipeline: parse → ground → dedupe → truncate → order."""
    parsed, diagnostics = parse_action_items_json(
        raw_json, max_output_tokens=max_output_tokens
    )
    grounded, ground_diag = ground_action_items(parsed, bounded_transcript)
    diagnostics["items_ungrounded_dropped"] = ground_diag["items_ungrounded_dropped"]
    diagnostics["quotes_nulled"] = ground_diag["quotes_nulled"]
    deduped, dup_removed = dedupe_action_items(grounded)
    diagnostics["items_duplicate_removed"] = dup_removed
    truncated, trunc_count = truncate_action_items(deduped)
    diagnostics["items_truncated"] = trunc_count
    committed = order_action_items(truncated, bounded_transcript)
    counts = build_counts_by_type(committed)
    diagnostics["counts_by_type"] = counts
    diagnostics["items_committed"] = sum(counts.values())
    return committed, diagnostics


def is_v1_action_items_payload(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    schema_id = payload.get("schema_id")
    if schema_id == LLM_ACTION_ITEMS_SCHEMA_ID:
        return False
    if schema_id == LLM_ACTION_ITEMS_SCHEMA_ID_V1:
        return True
    # Legacy artifacts without schema_id but with items and no record_type.
    items = payload.get("items")
    if not isinstance(items, list):
        return False
    if schema_id not in (None, "", LLM_ACTION_ITEMS_SCHEMA_ID_V1):
        return False
    if not items:
        return schema_id == LLM_ACTION_ITEMS_SCHEMA_ID_V1 or schema_id in (None, "")
    for item in items:
        if isinstance(item, dict) and "record_type" in item:
            return False
    return True


def coerce_v1_action_items_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """In-memory coerce v1 → action_item rows; stamp compat, keep original schema."""
    out = dict(payload)
    items_in = out.get("items") or []
    coerced: List[Dict[str, Any]] = []
    if isinstance(items_in, list):
        for item in items_in:
            if not isinstance(item, dict):
                continue
            entry = dict(item)
            entry["record_type"] = "action_item"
            coerced.append(entry)
    out["items"] = coerced
    provenance = dict(out.get("provenance") or {})
    provenance["compat"] = "v1_coerced"
    out["provenance"] = provenance
    return out


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
