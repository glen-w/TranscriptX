"""Opt-in web lookup for public event dates (query only; never sends transcript body)."""

from __future__ import annotations

import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Sequence
import httpx

from transcriptx.core.utils.rename.suggestions.models import RawRenameCue
from transcriptx.core.utils.rename.suggestions.transcript_cues import (
    parse_date_from_text,
)

_DDG_URL = "https://html.duckduckgo.com/html/"
_YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
_YOUTUBE_API_KEY_ENV = "TRANSCRIPTX_YOUTUBE_API_KEY"
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


def build_youtube_web_query(*, title: str, filename: str = "") -> str:
    """Short DuckDuckGo query biased toward YouTube watch pages (no API key)."""
    stem = Path(filename).stem if filename else ""
    base = (title.strip() or stem.replace("_", " ")).strip()[:80]
    if not base:
        return ""
    query = f"{base} site:youtube.com"
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


def resolve_youtube_api_key() -> str:
    """Operator-supplied YouTube Data API key. Never read from transcript text."""
    return os.environ.get(_YOUTUBE_API_KEY_ENV, "").strip()


def parse_youtube_published_at(value: str) -> date | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        return datetime.fromisoformat(raw).date()
    except ValueError:
        parsed, _ = parse_date_from_text(value)
        return parsed


def fetch_youtube_api_cue(
    query: str,
    *,
    api_key: str,
    timeout: float = 8.0,
    http_get=httpx.get,
) -> RawRenameCue | None:
    """YouTube Data API v3 search + videos. Short title query only."""
    q = (query or "").strip()[:80]
    key = (api_key or "").strip()
    if not q or not key:
        return None
    try:
        search = http_get(
            _YOUTUBE_SEARCH_URL,
            params={
                "part": "snippet",
                "type": "video",
                "maxResults": "3",
                "q": q,
                "key": key,
            },
            timeout=timeout,
        )
    except httpx.HTTPError:
        return None
    if getattr(search, "status_code", 0) != 200:
        return None
    try:
        payload = search.json()
    except ValueError:
        return None
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not items:
        return None
    video_ids: list[str] = []
    titles: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        vid = ((item.get("id") or {}) if isinstance(item.get("id"), dict) else {}).get(
            "videoId"
        )
        snippet = item.get("snippet") if isinstance(item.get("snippet"), dict) else {}
        if vid:
            video_ids.append(str(vid))
            titles[str(vid)] = str(snippet.get("title") or "")
    if not video_ids:
        return None
    try:
        videos = http_get(
            _YOUTUBE_VIDEOS_URL,
            params={
                "part": "snippet",
                "id": ",".join(video_ids),
                "key": key,
            },
            timeout=timeout,
        )
    except httpx.HTTPError:
        return None
    if getattr(videos, "status_code", 0) != 200:
        return None
    try:
        video_payload = videos.json()
    except ValueError:
        return None
    vitems = video_payload.get("items") if isinstance(video_payload, dict) else None
    if not isinstance(vitems, list):
        return None
    for item in vitems:
        if not isinstance(item, dict):
            continue
        snippet = item.get("snippet") if isinstance(item.get("snippet"), dict) else {}
        published = parse_youtube_published_at(str(snippet.get("publishedAt") or ""))
        if published is None:
            continue
        title = str(snippet.get("title") or titles.get(str(item.get("id") or ""), ""))
        return RawRenameCue(
            basis="web",
            confidence="likely",
            detail=f"YouTube Data API: {title[:80] or 'video'}",
            event_date=published,
            title=title,
            _priority=2,
        )
    return None


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


def fetch_web_cue_from_title(
    *,
    title: str,
    filename: str = "",
    host_names: Sequence[str] = (),
    timeout: float = 8.0,
) -> RawRenameCue | None:
    """Try YouTube Data API (opt-in key), then YouTube-biased DDG, then general."""
    api_key = resolve_youtube_api_key()
    if api_key:
        api_query = (title.strip() or Path(filename).stem.replace("_", " ")).strip()[
            :80
        ]
        cue = fetch_youtube_api_cue(api_query, api_key=api_key, timeout=timeout)
        if cue is not None:
            return cue
    yt_query = build_youtube_web_query(title=title, filename=filename)
    if yt_query:
        cue = fetch_web_cue(yt_query, timeout=timeout)
        if cue is not None:
            return cue
    general = build_web_query(title=title, host_names=host_names, filename=filename)
    return fetch_web_cue(general, timeout=timeout)
