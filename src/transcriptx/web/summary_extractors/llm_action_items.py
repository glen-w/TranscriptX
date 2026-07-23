"""Summary extractor for llm_action_items analysis."""

from __future__ import annotations

from typing import Any, Dict

from transcriptx.core.analysis.llm_support.action_items_contract import (
    RECORD_TYPE_LABELS,
    RECORD_TYPES,
    STATUSES,
    build_counts_by_type,
)

from . import register_extractor


def extract_llm_action_items_summary(
    data: Dict[str, Any], summary: Dict[str, Any]
) -> None:
    items = data.get("items")
    if not isinstance(items, list):
        return
    typed_items = [item for item in items if isinstance(item, dict)]
    summary["key_metrics"]["Meeting extracts"] = len(typed_items)
    type_counts = build_counts_by_type(typed_items)
    for record_type in RECORD_TYPES:
        count = type_counts.get(record_type, 0)
        if count:
            summary["key_metrics"][RECORD_TYPE_LABELS[record_type]] = count
    status_counts = {status: 0 for status in STATUSES}
    for item in typed_items:
        status = item.get("status")
        if status in status_counts:
            status_counts[str(status)] += 1
    for status, count in status_counts.items():
        if count:
            summary["key_metrics"][f"{status.title()} items"] = count


register_extractor("llm_action_items", extract_llm_action_items_summary)
