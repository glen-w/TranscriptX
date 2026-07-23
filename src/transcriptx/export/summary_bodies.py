"""JSON → markdown adapters for export summary bodies (meta-stripped)."""

from __future__ import annotations

from typing import Any


def strip_summary_markdown(md: str) -> str:
    """Drop generated top-level titles and provenance footers from markdown bodies."""
    lines = md.splitlines()
    body_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped == "---":
            break
        # Drop document H1 only; keep ##+ for rendered section headings.
        if stripped.startswith("# ") and not stripped.startswith("##"):
            continue
        body_lines.append(line)
    return "\n".join(body_lines).strip()


def _commitments_markdown(payload: dict[str, Any]) -> str:
    """Export-only commitments section (core summary MD omits this for UI Insights)."""
    commitments = payload.get("commitments") or {}
    commitment_items = (
        commitments.get("items") if isinstance(commitments, dict) else None
    ) or []
    commitment_lines: list[str] = []
    if isinstance(commitment_items, list):
        for item in commitment_items:
            if not isinstance(item, dict):
                continue
            owner = str(item.get("owner_display") or item.get("owner") or "").strip()
            action = str(item.get("action") or "").strip()
            if not action:
                continue
            if owner:
                commitment_lines.append(f"- **{owner}**: {action}")
            else:
                commitment_lines.append(f"- {action}")
    if not commitment_lines:
        return ""
    return "\n".join(["## Commitments / Next steps", *commitment_lines]).strip()


def executive_summary_markdown(payload: dict[str, Any]) -> str:
    """Build export markdown via core renderer (no meta chrome) + commitments."""
    from transcriptx.core.analysis.summary import render_summary_markdown

    try:
        rendered = render_summary_markdown(payload, include_meta=False)
        body = strip_summary_markdown(rendered)
    except Exception:
        body = ""

    # Legacy / alternate shapes when core renderer produces nothing useful.
    if not body or body.startswith("_No clear signal"):
        overview = payload.get("overview") or {}
        overview_text = ""
        if isinstance(overview, dict):
            overview_text = str(overview.get("paragraph") or "").strip()
        elif overview:
            overview_text = str(overview).strip()
        key_themes = payload.get("key_themes") or {}
        theme_bullets = (
            key_themes.get("bullets") if isinstance(key_themes, dict) else None
        ) or []
        tension_points = payload.get("tension_points") or {}
        tension_bullets = (
            tension_points.get("bullets") if isinstance(tension_points, dict) else None
        ) or []

        has_structured = bool(overview_text or theme_bullets or tension_bullets)
        if not has_structured:
            legacy = str(
                payload.get("summary") or payload.get("narrative") or ""
            ).strip()
            if legacy:
                return legacy
            return body

        # If core returned empty/no-signal but we have structured fields, rebuild
        # the content sections without meta (mirrors core body layout).
        lines: list[str] = []
        if overview_text:
            lines.extend(["## Overview", overview_text, ""])
        theme_lines: list[str] = []
        if isinstance(theme_bullets, list):
            for bullet in theme_bullets:
                if isinstance(bullet, dict):
                    text = str(bullet.get("text") or "").strip()
                else:
                    text = str(bullet or "").strip()
                if text:
                    theme_lines.append(f"- {text}")
        if theme_lines:
            lines.extend(["## Key themes", *theme_lines, ""])
        tension_lines: list[str] = []
        if isinstance(tension_bullets, list):
            for bullet in tension_bullets:
                if not isinstance(bullet, dict):
                    text = str(bullet or "").strip()
                    if text:
                        tension_lines.append(f"- {text}")
                    continue
                text = str(bullet.get("text") or "").strip()
                if text:
                    tension_lines.append(f"- {text}")
                anchor = bullet.get("anchor_quote") or {}
                if isinstance(anchor, dict):
                    speaker = str(anchor.get("speaker") or "").strip()
                    quote = str(anchor.get("quote") or "").strip()
                    if speaker or quote:
                        label = speaker or "Quote"
                        tension_lines.append(f"  - **{label}**: {quote}")
        if tension_lines:
            lines.extend(["## Tension points", *tension_lines, ""])
        body = "\n".join(lines).strip()

    commitments = _commitments_markdown(payload)
    if commitments:
        if body:
            return f"{body}\n\n{commitments}".strip()
        return commitments
    return body


def action_items_markdown(payload: dict[str, Any]) -> str:
    """Build export markdown via core action-items renderer (no provenance footer)."""
    from transcriptx.core.analysis.llm_support.action_items_render import (
        render_action_items_markdown,
    )

    try:
        rendered = render_action_items_markdown(payload, include_meta=False)
        body = strip_summary_markdown(rendered)
        if body:
            # Core uses italic "No action items found." — normalize for export.
            if body in {"_No action items found._", "*No action items found.*"}:
                return "No action items found."
            return body
    except Exception:
        pass

    items = payload.get("items") or []
    if not isinstance(items, list) or not items:
        return "No action items found."
    lines: list[str] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        lines.append(f"{index}. **{text}**")
        status = item.get("status")
        if status:
            lines.append(f"   - Status: {status}")
        owner = item.get("owner")
        if owner:
            lines.append(f"   - Owner: {owner}")
        deadline = item.get("deadline")
        if deadline:
            lines.append(f"   - Deadline: {deadline}")
        quote = item.get("quote")
        if quote:
            lines.append(f'   - Quote: "{quote}"')
        lines.append("")
    return "\n".join(lines).strip()


def summary_text_from_payload(payload: dict[str, Any], *, kind: str) -> str:
    if kind == "executive":
        return executive_summary_markdown(payload)
    if kind == "narrative_summary":
        return str(payload.get("narrative") or payload.get("summary") or "").strip()
    if kind == "llm_speaker_summary":
        return str(payload.get("summary") or "").strip()
    if kind == "llm_action_items":
        return action_items_markdown(payload)
    if kind == "llm_custom_qa":
        from transcriptx.core.analysis.llm_custom_qa.render import (
            render_custom_qa_markdown,
        )

        return render_custom_qa_markdown(payload).strip()
    return str(payload.get("summary") or payload.get("narrative") or "").strip()
