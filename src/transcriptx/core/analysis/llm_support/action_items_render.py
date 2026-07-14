"""Markdown rendering for action-item payloads (consumed by export too)."""

from __future__ import annotations

from typing import Any, Dict

__all__ = [
    "escape_markdown",
    "render_action_items_markdown",
]


def escape_markdown(text: str) -> str:
    """Escape dynamic text for safe Markdown rendering."""
    for char in ("\\", "[", "]", "*", "_", "`", "#", "<", ">"):
        text = text.replace(char, f"\\{char}")
    return text


def render_action_items_markdown(
    payload: Dict[str, Any], *, include_meta: bool = True
) -> str:
    """Render action-items markdown.

    When ``include_meta`` is False, omit provenance footers (used by export).
    """
    lines = ["# Action Items", ""]
    items = payload.get("items") or []
    if not items:
        lines.append("_No action items found._")
    else:
        for index, item in enumerate(items, start=1):
            lines.append(f"{index}. **{escape_markdown(str(item.get('text', '')))}**")
            lines.append(f"   - Status: {escape_markdown(str(item.get('status', '')))}")
            owner = item.get("owner")
            lines.append(f"   - Owner: {escape_markdown(owner) if owner else '—'}")
            deadline = item.get("deadline")
            lines.append(
                f"   - Deadline: {escape_markdown(deadline) if deadline else '—'}"
            )
            quote = item.get("quote")
            if quote:
                lines.append(f'   - Quote: "{escape_markdown(str(quote))}"')
            confidence = item.get("confidence")
            if include_meta and confidence is not None:
                lines.append(f"   - Confidence: {float(confidence):.2f}")
            lines.append("")
    if include_meta:
        prov = payload.get("provenance") or {}
        if prov:
            lines.append("---")
            lines.append(f"Prompt version: {prov.get('prompt_version', '')}")
            lines.append(f"Model: {prov.get('model', '')}")
    lines.append("")
    return "\n".join(lines)
