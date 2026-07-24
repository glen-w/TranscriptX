"""Meeting-extract feature contract (llm_action_items).

Schema validation, grounding, dedupe, ordering, bounds, legacy coerce, and
cache identity. Rendering lives in ``action_items_render``.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from transcriptx.core.analysis.llm_support.action_items_guidance import (
    format_invalid_json_error,
    format_oversized_output_error,
)
from transcriptx.core.analysis.llm_support.hashing import sha256_canonical_json
from transcriptx.core.analysis.llm_support.json_parse import (
    loads_llm_json,
    strip_json_fence,
)
from transcriptx.core.llm.errors import LLMResponseError
from transcriptx.core.utils.logger import get_logger

logger = get_logger()

__all__ = [
    "LLM_ACTION_ITEMS_SCHEMA_ID",
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

LLM_ACTION_ITEMS_SCHEMA_ID = "transcriptx.llm_action_items.v1"
LLM_ACTION_ITEMS_RENDER_CONTRACT_ID = "transcriptx.llm_action_items.render.v2"
LLM_ACTION_ITEMS_GROUP_SCHEMA_VERSION = 1

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
# Common local-LLM aliases → canonical keys before validation.
_ACTION_ITEM_KEY_ALIASES = {
    "type": "record_type",
    "item_type": "record_type",
    "kind": "record_type",
    "description": "text",
    "title": "text",
    "summary": "text",
    "action": "text",
    "assignee": "owner",
    "who": "owner",
    "due": "deadline",
    "due_date": "deadline",
    "evidence": "quote",
    "citation": "quote",
    "source": "quote",
    "score": "confidence",
    "certainty": "confidence",
}
_VALID_RECORD_TYPES = frozenset(RECORD_TYPES)
_VALID_ACTION_STATUSES = frozenset(STATUSES)
_RECORD_TYPE_ALIASES = {
    "task": "action_item",
    "todo": "action_item",
    "to-do": "action_item",
    "to_do": "action_item",
    "action": "action_item",
    "actions": "action_item",
    "question": "open_question",
    "unresolved_question": "open_question",
    "unanswered_question": "open_question",
    "open question": "open_question",
    "conclusion": "decision",
    "decided": "decision",
    "decision_made": "decision",
    "promise": "commitment",
    "pledge": "commitment",
    "undertaking": "commitment",
    "suggestion": "proposal",
    "idea": "proposal",
    "recommendation": "proposal",
}
_STATUS_ALIASES = {
    "pending": "open",
    "incomplete": "open",
    "todo": "open",
    "to-do": "open",
    "in_progress": "open",
    "in-progress": "open",
    "ongoing": "open",
    "completed": "done",
    "finished": "done",
    "resolved": "done",
    "closed": "done",
    "complete": "done",
    "unknown": "unclear",
    "n/a": "unclear",
    "na": "unclear",
    "none": "unclear",
    "unspecified": "unclear",
}
_CONFIDENCE_LABELS = {
    "high": 0.9,
    "medium": 0.6,
    "med": 0.6,
    "mid": 0.6,
    "low": 0.3,
}
_DEFAULT_CONFIDENCE = 0.5
_MIN_SALVAGED_QUOTE_CHARS = 20
_RECORD_TYPE_RANK = {name: index for index, name in enumerate(RECORD_TYPE_ORDER)}
_DONE_EVIDENCE_RE = re.compile(
    r"\b(?:"
    + "|".join(re.escape(word) for word in sorted(DONE_EVIDENCE_LEXICON))
    + r")\b",
    re.IGNORECASE,
)
_ELLIPSIS_SPLIT_RE = re.compile(r"\s*(?:\.\.\.|…)\s*")


def empty_counts_by_type() -> Dict[str, int]:
    return {record_type: 0 for record_type in RECORD_TYPES}


def empty_diagnostics() -> Dict[str, Any]:
    return {
        "items_raw": 0,
        "items_parsed_valid": 0,
        "record_type_defaulted": 0,
        "record_type_aliased": 0,
        "status_aliased": 0,
        "confidence_defaulted": 0,
        "confidence_coerced": 0,
        "extra_fields_stripped": 0,
        "items_invalid_dropped": 0,
        "status_unsupported_dropped": 0,
        "items_ungrounded_dropped": 0,
        "quotes_nulled": 0,
        "quotes_salvaged": 0,
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


def _validate_confidence(value: Any) -> Tuple[Optional[float], Optional[str]]:
    """Return (confidence, coerce_tag) where coerce_tag is defaulted/coerced/None."""
    if value is None:
        return _DEFAULT_CONFIDENCE, "defaulted"
    if isinstance(value, bool):
        return None, None
    if isinstance(value, (int, float)):
        confidence = float(value)
        if not (
            confidence == confidence
            and confidence != float("inf")
            and confidence != float("-inf")
        ):
            return None, None
        if 0.0 <= confidence <= 1.0:
            return confidence, None
        # Local models often emit 0-100 percentages (typically integers >= 2).
        if 2.0 <= confidence <= 100.0:
            return confidence / 100.0, "coerced"
        return None, None
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if not cleaned:
            return _DEFAULT_CONFIDENCE, "defaulted"
        if cleaned in _CONFIDENCE_LABELS:
            return _CONFIDENCE_LABELS[cleaned], "coerced"
        percent = cleaned.endswith("%")
        if percent:
            cleaned = cleaned[:-1].strip()
        try:
            numeric = float(cleaned)
        except ValueError:
            return None, None
        if percent and 0.0 <= numeric <= 100.0:
            return numeric / 100.0, "coerced"
        return _validate_confidence(numeric)
    return None, None


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


def _normalise_raw_action_item(raw: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    """Map common field aliases and drop unknown keys. Returns (item, extras_count)."""
    normalised: Dict[str, Any] = {}
    extras = 0
    # Prefer explicit canonical keys over aliases when both are present.
    for key, value in raw.items():
        if not isinstance(key, str):
            extras += 1
            continue
        if key in _ACTION_ITEM_KEYS:
            normalised[key] = value
    for key, value in raw.items():
        if not isinstance(key, str) or key in _ACTION_ITEM_KEYS:
            continue
        canonical = _ACTION_ITEM_KEY_ALIASES.get(key)
        if canonical is None:
            extras += 1
            continue
        if canonical not in normalised:
            normalised[canonical] = value
    return normalised, extras


def _canonical_record_type(
    value: Any,
) -> Tuple[Optional[str], bool, bool]:
    """Return (record_type, defaulted, aliased). None means invalid."""
    if value is None:
        return "action_item", True, False
    if not isinstance(value, str):
        return None, False, False
    candidate = value.strip()
    if not candidate:
        return "action_item", True, False
    lowered = candidate.lower().replace("-", "_")
    spaced = candidate.lower()
    if candidate in _VALID_RECORD_TYPES:
        return candidate, False, False
    if lowered in _VALID_RECORD_TYPES:
        return lowered, False, True
    alias = _RECORD_TYPE_ALIASES.get(lowered) or _RECORD_TYPE_ALIASES.get(spaced)
    if alias is not None:
        return alias, False, True
    return None, False, False


def _canonical_status(value: Any) -> Tuple[Optional[str], bool]:
    """Return (status, aliased). None means unsupported."""
    if value is None:
        return "unclear", True
    if isinstance(value, str):
        candidate = value.strip().lower()
        if not candidate:
            return "unclear", True
        if candidate in _VALID_ACTION_STATUSES:
            return candidate, candidate != value.strip()
        alias = _STATUS_ALIASES.get(candidate)
        if alias is not None:
            return alias, True
    return None, False


def _validate_action_item(
    raw: Any,
    *,
    index: int,
) -> Tuple[Optional[Dict[str, Any]], Optional[str], Dict[str, int]]:
    """Return (item, drop_reason, coerce_counters)."""
    counters = {
        "record_type_defaulted": 0,
        "record_type_aliased": 0,
        "status_aliased": 0,
        "confidence_defaulted": 0,
        "confidence_coerced": 0,
        "extra_fields_stripped": 0,
    }
    if not isinstance(raw, dict):
        return None, "items_invalid_dropped", counters

    normalised, extras = _normalise_raw_action_item(raw)
    if extras:
        counters["extra_fields_stripped"] = 1

    record_type, defaulted, aliased = _canonical_record_type(
        normalised.get("record_type")
    )
    if record_type is None:
        return None, "items_invalid_dropped", counters
    if defaulted:
        counters["record_type_defaulted"] = 1
    if aliased:
        counters["record_type_aliased"] = 1

    text = normalised.get("text")
    if not isinstance(text, str) or not text.strip():
        return None, "items_invalid_dropped", counters

    owner = _optional_string_field(normalised.get("owner"), coerce_scalars=True)
    deadline = _optional_string_field(normalised.get("deadline"), coerce_scalars=True)
    status, status_aliased = _canonical_status(normalised.get("status"))
    if status is None:
        return None, "status_unsupported_dropped", counters
    if status_aliased:
        counters["status_aliased"] = 1
    quote = _optional_string_field(normalised.get("quote"), coerce_scalars=False)
    confidence, confidence_tag = _validate_confidence(normalised.get("confidence"))
    if confidence is None:
        return None, "items_invalid_dropped", counters
    if confidence_tag == "defaulted":
        counters["confidence_defaulted"] = 1
    elif confidence_tag == "coerced":
        counters["confidence_coerced"] = 1

    if (
        status == "done"
        and record_type in TYPES_REQUIRING_DONE_EVIDENCE
        and not _has_done_evidence(text, quote)
    ):
        return None, "status_unsupported_dropped", counters

    item = {
        "record_type": record_type,
        "text": text.strip(),
        "owner": owner,
        "deadline": deadline,
        "status": status,
        "quote": quote,
        "confidence": confidence,
        "_model_index": index,
        "_record_type_defaulted": defaulted,
    }
    return item, None, counters


def _find_items_array_body_start(candidate: str) -> Optional[int]:
    """Return index just after ``[`` of the top-level ``items`` array, if present."""
    key_match = re.search(r'"items"\s*:', candidate)
    if key_match is None:
        return None
    index = key_match.end()
    while index < len(candidate) and candidate[index] in " \t\r\n":
        index += 1
    if index >= len(candidate) or candidate[index] != "[":
        return None
    return index + 1


def _recover_truncated_action_items(candidate: str) -> Optional[List[Any]]:
    """Salvage complete ``items`` elements from truncated meeting-extract JSON.

    Local models often hit ``num_predict`` mid-object (unterminated string).
    When at least one complete element can be ``raw_decode``d from the array,
    return those elements so the module can still publish artifacts. Returns
    ``None`` when nothing salvageable is found.
    """
    body_start = _find_items_array_body_start(candidate)
    if body_start is None:
        return None
    decoder = json.JSONDecoder()
    items: List[Any] = []
    index = body_start
    length = len(candidate)
    while index < length:
        while index < length and candidate[index] in " \t\r\n":
            index += 1
        if index >= length:
            break
        if candidate[index] == "]":
            break
        if candidate[index] == ",":
            index += 1
            continue
        try:
            value, end = decoder.raw_decode(candidate, index)
        except json.JSONDecodeError:
            break
        items.append(value)
        index = end
        while index < length and candidate[index] in " \t\r\n":
            index += 1
        if index < length and candidate[index] == ",":
            index += 1
            continue
        break
    if not items:
        return None
    return items


def parse_action_items_json(
    text: str,
    *,
    max_output_tokens: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Parse meeting-extract JSON with per-record isolation.

    Top-level failures raise ``LLMResponseError``. Invalid items are dropped
    and counted in diagnostics. Truncated arrays with at least one complete
    item are salvaged and flagged via ``diagnostics["output_truncated"]``.
    """
    diagnostics = empty_diagnostics()
    candidate = strip_json_fence(text)
    if max_output_tokens is not None and max_output_tokens > 0:
        char_limit = max_output_tokens * 4
        if len(candidate) > char_limit:
            diagnostics["output_truncated"] = 1
            raise LLMResponseError(
                format_oversized_output_error(
                    length=len(candidate), char_limit=char_limit
                )
            )
    try:
        data = loads_llm_json(text)
    except json.JSONDecodeError as exc:
        recovered_items = _recover_truncated_action_items(candidate)
        if recovered_items is None:
            raise LLMResponseError(format_invalid_json_error(exc)) from exc
        data = {"items": recovered_items}
        diagnostics["output_truncated"] = 1
        logger.warning(
            "llm_action_items salvaged %s complete item(s) from truncated JSON; "
            "raise effort/model before re-running if extracts look incomplete",
            len(recovered_items),
        )
    if not isinstance(data, dict):
        raise LLMResponseError("Action items output JSON must be an object")
    # Keep ``items`` even when models wrap with prose metadata keys.
    if "items" not in data and isinstance(data.get("action_items"), list):
        data = {**data, "items": data.get("action_items")}
    if "items" not in data and isinstance(data.get("extracts"), list):
        data = {**data, "items": data.get("extracts")}
    items_raw = data.get("items")
    if not isinstance(items_raw, list):
        raise LLMResponseError("Action items output missing 'items' array")

    diagnostics["items_raw"] = len(items_raw)
    parsed: List[Dict[str, Any]] = []
    for index, raw_item in enumerate(items_raw):
        item, drop_reason, counters = _validate_action_item(raw_item, index=index)
        for key, count in counters.items():
            if count:
                diagnostics[key] = int(diagnostics.get(key, 0)) + count
        if item is None:
            assert drop_reason is not None
            diagnostics[drop_reason] = int(diagnostics.get(drop_reason, 0)) + 1
            continue
        item.pop("_record_type_defaulted", False)
        parsed.append(item)

    diagnostics["items_parsed_valid"] = len(parsed)
    return parsed, diagnostics


def _substring_offset(haystack: str, needle: str) -> Optional[int]:
    if not needle:
        return None
    idx = haystack.find(needle)
    return idx if idx >= 0 else None


def _salvage_quote_span(quote: str, normalised_transcript: str) -> Optional[str]:
    """Recover a contiguous transcript span from an ellipsis-joined / padded quote."""
    quote_norm = _normalise_whitespace(quote)
    if not quote_norm:
        return None
    if _substring_offset(normalised_transcript, quote_norm) is not None:
        return quote_norm

    parts = [
        _normalise_whitespace(part)
        for part in _ELLIPSIS_SPLIT_RE.split(quote_norm)
        if _normalise_whitespace(part)
    ]
    candidates = [part for part in parts if len(part) >= _MIN_SALVAGED_QUOTE_CHARS]
    # Prefer the longest matching fragment so evidence stays specific.
    candidates.sort(key=len, reverse=True)
    for part in candidates:
        if _substring_offset(normalised_transcript, part) is not None:
            return part

    # Sliding window over whitespace tokens when the model lightly paraphrases edges.
    tokens = quote_norm.split()
    if len(tokens) < 4:
        return None
    for window in range(len(tokens), 3, -1):
        for start in range(0, len(tokens) - window + 1):
            span = " ".join(tokens[start : start + window])
            if len(span) < _MIN_SALVAGED_QUOTE_CHARS:
                continue
            if _substring_offset(normalised_transcript, span) is not None:
                return span
    return None


def ground_action_items(
    items: List[Dict[str, Any]],
    bounded_transcript: str,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Ground quotes and text against the bounded transcript block.

    Record-type agnostic. Never rewrites record_type, text, owner, deadline,
    or status. May null ungrounded quotes, salvage ellipsis-joined quotes to a
    contiguous transcript span, and scale confidence.
    """
    normalised_transcript = _normalise_whitespace(bounded_transcript)
    grounded: List[Dict[str, Any]] = []
    quotes_nulled = 0
    quotes_salvaged = 0
    ungrounded_dropped = 0
    for item in items:
        entry = dict(item)
        text_norm = _normalise_whitespace(entry["text"])
        text_grounded = _substring_offset(normalised_transcript, text_norm) is not None
        quote_original = entry.get("quote")
        quote_grounded = False
        if quote_original:
            quote_norm = _normalise_whitespace(quote_original)
            if _substring_offset(normalised_transcript, quote_norm) is not None:
                quote_grounded = True
            else:
                salvaged = _salvage_quote_span(quote_original, normalised_transcript)
                if salvaged is not None:
                    entry["quote"] = salvaged
                    quote_grounded = True
                    quotes_salvaged += 1
                else:
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
        "quotes_salvaged": quotes_salvaged,
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
    diagnostics["quotes_salvaged"] = ground_diag["quotes_salvaged"]
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
    """True for unstamped payloads whose items lack ``record_type``.

    Surviving callers: group aggregation
    (``aggregation/llm.py::_resolve_member_payload``) and Insights caption
    (``web/blocks/implementations/insights.py``). Epoch-1 stamped
    ``transcriptx.llm_action_items.v1`` payloads return False.
    """
    if not isinstance(payload, dict):
        return False
    schema_id = payload.get("schema_id")
    if schema_id not in (None, ""):
        return False
    items = payload.get("items")
    if not isinstance(items, list):
        return False
    if not items:
        return True
    for item in items:
        if isinstance(item, dict) and "record_type" in item:
            return False
    return True


def coerce_v1_action_items_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """In-memory coerce legacy rows → ``action_item``; stamp compat provenance."""
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
