"""Highlight rendering helpers for transcript text."""

from __future__ import annotations

import html


def render_highlight_html(text: str, query: str | None) -> str:
    """Return HTML-safe text with query matches wrapped in <mark>."""
    if not text:
        return ""
    if not query:
        return text
    lower_text = text.lower()
    lower_query = query.lower().strip()
    if not lower_query:
        return text
    spans: list[tuple[int, int]] = []
    pos = 0
    while True:
        idx = lower_text.find(lower_query, pos)
        if idx == -1:
            break
        spans.append((idx, idx + len(lower_query)))
        pos = idx + len(lower_query)
    if not spans:
        return text
    rendered_parts: list[str] = []
    cursor = 0
    for span_start, span_end in spans:
        rendered_parts.append(html.escape(text[cursor:span_start]))
        rendered_parts.append(f"<mark>{html.escape(text[span_start:span_end])}</mark>")
        cursor = span_end
    rendered_parts.append(html.escape(text[cursor:]))
    return "".join(rendered_parts)
