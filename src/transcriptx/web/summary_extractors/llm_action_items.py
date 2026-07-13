"""Summary extractor for llm_action_items analysis."""

from __future__ import annotations

from typing import Any, Dict

from . import register_extractor


def extract_llm_action_items_summary(
    data: Dict[str, Any], summary: Dict[str, Any]
) -> None:
    items = data.get("items")
    if not isinstance(items, list):
        return
    summary["key_metrics"]["Action items"] = len(items)
    status_counts = {"open": 0, "done": 0, "unclear": 0}
    for item in items:
        if not isinstance(item, dict):
            continue
        status = item.get("status")
        if status in status_counts:
            status_counts[str(status)] += 1
    for status, count in status_counts.items():
        if count:
            summary["key_metrics"][f"{status.title()} items"] = count


register_extractor("llm_action_items", extract_llm_action_items_summary)
