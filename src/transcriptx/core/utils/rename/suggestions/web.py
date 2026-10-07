"""Opt-in web lookup for public event dates (query only; never sends transcript body)."""

from __future__ import annotations

import re
from datetime import date
from typing import Sequence
import httpx

from transcriptx.core.utils.rename.suggestions.models import RawRenameCue
from transcriptx.core.utils.rename.suggestions.transcript_cues import parse_date_from_text

_DDG_URL = "https://html.duckduckgo.com/html/"
_RESULT_SNIPPET = re.compile(
    r'class="result__snippet"[^>]*>([^<]+)',
    re.IGNORECASE,
)
_RESULT_TITLE = re.compile(
    r'class="result__a"[^>]*>([^<]+)',
    re.IGNORECASE,
)


def build_web_query(
    *,
    title: str,
    host_names: Sequence[str] = (),
    filename: str = "",
) -> str:
    """Build a short search query from title/host cues (not transcript text)."""
    parts: list[str] = []
    if title.strip():
        parts.append(title.strip()[:80])
    for name in host_names[:2]:
        n = (name or "").strip()
        if n and n not in parts:
            parts.append(n[:40])
    blob = " ".join(parts).strip()
    if "webinar" not in blob.lower() and "webcast" not in blob.lower():
        if "webinar" in (filename or "").lower():
            parts.append("webinar")
        elif title:
            parts.append("webinar")
    query = " ".join(parts).strip()
    return query[:120]


def parse_dates_from_html(html: str) -> tuple[date | None, str, str]:
    """Return (date, detail, matched_title) from DuckDuckGo HTML."""
    titles = _RESULT_TITLE.findall(html or "")
    snippets = _RESULT_SNIPPET.findall(html or "")
    for idx, snippet in enumerate(snippets[:8]):
        parsed, _ = parse_date_from_text(snippet)
        if parsed is not None:
            title = titles[idx] if idx < len(titles) else ""
            detail = f"Web result: {title[:80] or 'snippet'}"
            return parsed, detail, title
    for title in titles[:5]:
        parsed, _ = parse_date_from_text(title)
        if parsed is not None:
            return parsed, f"Web result: {title[:80]}", title
    return None, "", ""


def fetch_web_cue(query: str, *, timeout: float = 8.0) -> RawRenameCue | None:
    q = (query or "").strip()
    if not q:
        return None
    try:
        response = httpx.get(
            _DDG_URL,
            params={"q": q},
            headers={"User-Agent": "TranscriptX/1.0 (rename suggestions)"},
            timeout=timeout,
            follow_redirects=True,
        )
    except httpx.HTTPError:
        return None
    if response.status_code != 200:
        return None
    event_date, detail, title = parse_dates_from_html(response.text)
    if event_date is None:
        return None
    return RawRenameCue(
        basis="web",
        confidence="likely",
        detail=detail or "Web search date",
        event_date=event_date,
        title=title,
        _priority=2,
    )
