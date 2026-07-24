"""Frozen llm_action_items v2 contract fixtures (B10).

Canonical enums/labels/bounds live in
``transcriptx.core.analysis.llm_support.action_items_contract``.
This module documents the artifact shape for golden tests.
"""

from __future__ import annotations

from typing import Any, Dict

from transcriptx.core.analysis.llm_support.action_items_contract import (
    EMPTY_EXTRACTS_MESSAGE,
    HUMAN_REVIEW_BANNER,
    LLM_ACTION_ITEMS_GROUP_SCHEMA_VERSION,
    LLM_ACTION_ITEMS_RENDER_CONTRACT_ID,
    LLM_ACTION_ITEMS_SCHEMA_ID,
    MAX_ITEMS_PER_TYPE,
    MAX_ITEMS_TOTAL,
    RECORD_TYPE_LABELS,
    RECORD_TYPE_ORDER,
    RECORD_TYPES,
    STATUSES,
    TITLE_MEETING_EXTRACTS,
    empty_counts_by_type,
    empty_diagnostics,
)

# Explicit top-level keys for committed v2 JSON artifacts (unknown keys rejected
# on model *output* parse; committed artifacts may include richer provenance).
V2_ARTIFACT_TOP_LEVEL_KEYS = frozenset(
    {
        "schema_id",
        "module_version",
        "render_contract_id",
        "module",
        "items",
        "diagnostics",
        "input_coverage",
        "provenance",
    }
)

V2_ITEM_KEYS = frozenset(
    {"record_type", "text", "owner", "deadline", "status", "quote", "confidence"}
)

V2_DIAGNOSTIC_KEYS = frozenset(
    {
        "items_raw",
        "items_parsed_valid",
        "record_type_defaulted",
        "record_type_aliased",
        "status_aliased",
        "confidence_defaulted",
        "confidence_coerced",
        "extra_fields_stripped",
        "items_invalid_dropped",
        "status_unsupported_dropped",
        "items_ungrounded_dropped",
        "quotes_nulled",
        "quotes_salvaged",
        "items_duplicate_removed",
        "items_truncated",
        "output_truncated",
        "counts_by_type",
        "items_committed",
    }
)

GROUP_SESSION_COUNT_COLUMNS = (
    "item_count",
    "count_decision",
    "count_commitment",
    "count_action_item",
    "count_proposal",
    "count_open_question",
    "status_open",
    "status_done",
    "status_unclear",
)


def example_v2_item(**overrides: Any) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "record_type": "action_item",
        "text": "Send the report",
        "owner": "Alice",
        "deadline": "Friday",
        "status": "open",
        "quote": "I will send the report by Friday.",
        "confidence": 0.9,
    }
    base.update(overrides)
    return base


def example_v2_artifact(
    items: list[Dict[str, Any]] | None = None,
    *,
    diagnostics: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    committed = list(items) if items is not None else [example_v2_item()]
    diag = empty_diagnostics() if diagnostics is None else diagnostics
    return {
        "schema_id": LLM_ACTION_ITEMS_SCHEMA_ID,
        "module_version": "2",
        "render_contract_id": LLM_ACTION_ITEMS_RENDER_CONTRACT_ID,
        "module": "llm_action_items",
        "items": committed,
        "diagnostics": diag,
        "input_coverage": {},
        "provenance": {
            "prompt_version": "5",
            "model": "fixture-model",
            "schema_id": LLM_ACTION_ITEMS_SCHEMA_ID,
            "module_version": "2",
            "render_contract_id": LLM_ACTION_ITEMS_RENDER_CONTRACT_ID,
        },
    }


def example_v1_artifact(
    items: list[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Legacy unstamped payload: no ``schema_id``, items lack ``record_type``.

    Detected by ``is_v1_action_items_payload``; live stamped artifacts are not.
    """
    legacy_items = items
    if legacy_items is None:
        legacy_items = [
            {
                "text": "Send the report",
                "owner": "Alice",
                "deadline": "Friday",
                "status": "open",
                "quote": "I will send the report by Friday.",
                "confidence": 0.9,
            }
        ]
    return {
        "module_version": "1",
        "module": "llm_action_items",
        "items": legacy_items,
        "diagnostics": {},
        "input_coverage": {},
        "provenance": {"prompt_version": "4", "model": "fixture-model"},
    }


__all__ = [
    "EMPTY_EXTRACTS_MESSAGE",
    "GROUP_SESSION_COUNT_COLUMNS",
    "HUMAN_REVIEW_BANNER",
    "LLM_ACTION_ITEMS_GROUP_SCHEMA_VERSION",
    "LLM_ACTION_ITEMS_RENDER_CONTRACT_ID",
    "LLM_ACTION_ITEMS_SCHEMA_ID",
    "MAX_ITEMS_PER_TYPE",
    "MAX_ITEMS_TOTAL",
    "RECORD_TYPE_LABELS",
    "RECORD_TYPE_ORDER",
    "RECORD_TYPES",
    "STATUSES",
    "TITLE_MEETING_EXTRACTS",
    "V2_ARTIFACT_TOP_LEVEL_KEYS",
    "V2_DIAGNOSTIC_KEYS",
    "V2_ITEM_KEYS",
    "empty_counts_by_type",
    "empty_diagnostics",
    "example_v1_artifact",
    "example_v2_artifact",
    "example_v2_item",
]
