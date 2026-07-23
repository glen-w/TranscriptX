"""Markdown rendering for meeting-extract payloads (consumed by export too)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from transcriptx.core.analysis.llm_support.action_items_contract import (
    EMPTY_EXTRACTS_MESSAGE,
    HUMAN_REVIEW_BANNER,
    LLM_ACTION_ITEMS_RENDER_CONTRACT_ID,
    RECORD_TYPE_LABELS,
    RECORD_TYPE_ORDER,
    TITLE_MEETING_EXTRACTS,
)

__all__ = [
    "escape_markdown",
    "normalise_render_text",
    "render_action_items_markdown",
]


def escape_markdown(text: str) -> str:
    """Escape dynamic text for safe Markdown rendering."""
    for char in ("\\", "[", "]", "*", "_", "`", "#", "<", ">"):
        text = text.replace(char, f"\\{char}")
    return text


def normalise_render_text(value: Any) -> Optional[str]:
    """Collapse multiline / noisy whitespace for owner, deadline, and quote."""
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    normalised = " ".join(value.split())
    return normalised or None


def render_action_items_markdown(
    payload: Dict[str, Any], *, include_meta: bool = True
) -> str:
    """Render meeting-extracts markdown (render contract v2).

    When ``include_meta`` is False, omit provenance footers (used by export)
    but still include the human-review banner.
    """
    lines = [f"# {TITLE_MEETING_EXTRACTS}", "", HUMAN_REVIEW_BANNER, ""]
    items = payload.get("items") or []
    if not isinstance(items, list):
        items = []

    by_type: Dict[str, List[Dict[str, Any]]] = {
        record_type: [] for record_type in RECORD_TYPE_ORDER
    }
    for item in items:
        if not isinstance(item, dict):
            continue
        record_type = str(item.get("record_type") or "action_item")
        if record_type not in by_type:
            record_type = "action_item"
        by_type[record_type].append(item)

    emitted = False
    for record_type in RECORD_TYPE_ORDER:
        typed_items = by_type[record_type]
        if not typed_items:
            continue
        emitted = True
        lines.append(f"## {RECORD_TYPE_LABELS[record_type]}")
        lines.append("")
        for index, item in enumerate(typed_items, start=1):
            text = escape_markdown(str(item.get("text", "")))
            lines.append(f"{index}. **{text}**")
            lines.append(
                f"   - Status: {escape_markdown(str(item.get('status', '')))}"
            )
            owner = normalise_render_text(item.get("owner"))
            lines.append(
                f"   - Owner: {escape_markdown(owner) if owner else '—'}"
            )
            deadline = normalise_render_text(item.get("deadline"))
            lines.append(
                f"   - Deadline: {escape_markdown(deadline) if deadline else '—'}"
            )
            quote = normalise_render_text(item.get("quote"))
            if quote:
                lines.append(f'   - Quote: "{escape_markdown(quote)}"')
            confidence = item.get("confidence")
            if include_meta and confidence is not None:
                lines.append(f"   - Confidence: {float(confidence):.2f}")
            lines.append("")

    if not emitted:
        lines.append(f"_{EMPTY_EXTRACTS_MESSAGE}_")
        lines.append("")

    if include_meta:
        prov = payload.get("provenance") or {}
        lines.append("---")
        render_id = (
            payload.get("render_contract_id")
            or prov.get("render_contract_id")
            or LLM_ACTION_ITEMS_RENDER_CONTRACT_ID
        )
        lines.append(f"Render contract: {render_id}")
        lines.append(f"Prompt version: {prov.get('prompt_version', '')}")
        lines.append(f"Model: {prov.get('model', '')}")
    lines.append("")
    return "\n".join(lines)
