"""Optional LLM pass for rename event date and title."""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any, Mapping, Sequence

from transcriptx.core.llm.llm_client import LLMClient
from transcriptx.core.utils.rename.suggestions.models import RawRenameCue
from transcriptx.core.utils.rename.suggestions.transcript_cues import build_cue_excerpt

RENAME_LLM_SUGGESTION_COUNT = 3

RENAME_LLM_INSTRUCTION = (
    "Extract public event dates and short file-name titles from the excerpt. "
    f"Reply with JSON only. Provide exactly {RENAME_LLM_SUGGESTION_COUNT} distinct "
    "suggestions with different titles."
)

_SYSTEM = (
    "You read a short excerpt from a webinar or meeting transcript and suggest "
    "metadata for a library file name. Reply with JSON only."
)


def _parse_llm_payload(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_suggestion_row(row: Mapping[str, Any], *, excerpt: str) -> RawRenameCue | None:
    title = str(row.get("title") or "").strip()
    quote = str(row.get("quote") or "").strip()
    event_date: date | None = None
    ed_raw = row.get("event_date")
    if isinstance(ed_raw, str) and ed_raw.strip():
        try:
            event_date = date.fromisoformat(ed_raw.strip()[:10])
        except ValueError:
            event_date = None
    if event_date is not None:
        if not quote or quote.lower() not in excerpt.lower():
            event_date = None
    if event_date is None and not title:
        return None
    return RawRenameCue(
        basis="llm",
        confidence="possible" if event_date else "likely",
        detail="Local LLM metadata suggestion",
        event_date=event_date,
        title=title,
        quote=quote,
        _priority=4,
    )


def parse_llm_rename_cues(
    raw: str,
    *,
    excerpt: str,
    limit: int = RENAME_LLM_SUGGESTION_COUNT,
) -> list[RawRenameCue]:
    payload = _parse_llm_payload(raw)
    rows: list[Mapping[str, Any]] = []
    suggestions = payload.get("suggestions")
    if isinstance(suggestions, list):
        rows = [r for r in suggestions if isinstance(r, dict)]
    elif payload:
        rows = [payload]
    cues: list[RawRenameCue] = []
    seen: set[tuple[str, str | None]] = set()
    for row in rows:
        cue = _parse_suggestion_row(row, excerpt=excerpt)
        if cue is None:
            continue
        key = (cue.title.lower(), cue.event_date.isoformat() if cue.event_date else None)
        if key in seen:
            continue
        seen.add(key)
        cue.detail = f"Local LLM suggestion {len(cues) + 1}"
        cues.append(cue)
        if len(cues) >= limit:
            break
    return cues


def parse_llm_rename_cue(
    raw: str,
    *,
    excerpt: str,
) -> RawRenameCue | None:
    cues = parse_llm_rename_cues(raw, excerpt=excerpt, limit=1)
    return cues[0] if cues else None


def run_rename_llm(
    client: LLMClient,
    *,
    user_prompt: str,
    excerpt_for_quotes: str,
    temperature: float,
    max_tokens: int,
) -> list[RawRenameCue]:
    try:
        raw = client.generate(
            user_prompt,
            system=_SYSTEM,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format="json",
        )
    except Exception:
        return []
    return parse_llm_rename_cues(str(raw or ""), excerpt=excerpt_for_quotes)


def build_llm_excerpt(segments: Sequence[Mapping[str, Any]]) -> str:
    return build_cue_excerpt(segments)
