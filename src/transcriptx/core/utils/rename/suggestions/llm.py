"""Optional LLM pass for rename event date and title."""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any, Mapping, Sequence

from transcriptx.core.llm.llm_client import LLMClient
from transcriptx.core.utils.rename.suggestions.models import RawRenameCue
from transcriptx.core.utils.rename.suggestions.transcript_cues import build_cue_excerpt

RENAME_LLM_INSTRUCTION = (
    "Extract a public event date and short title for renaming a transcript file. "
    "Reply with JSON only."
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


def parse_llm_rename_cue(
    raw: str,
    *,
    excerpt: str,
) -> RawRenameCue | None:
    payload = _parse_llm_payload(raw)
    title = str(payload.get("title") or "").strip()
    quote = str(payload.get("quote") or "").strip()
    event_date: date | None = None
    ed_raw = payload.get("event_date")
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


def run_rename_llm(
    client: LLMClient,
    *,
    user_prompt: str,
    excerpt_for_quotes: str,
    temperature: float,
    max_tokens: int,
) -> RawRenameCue | None:
    try:
        raw = client.generate(
            user_prompt,
            system=_SYSTEM,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format="json",
        )
    except Exception:
        return None
    return parse_llm_rename_cue(str(raw or ""), excerpt=excerpt_for_quotes)


def build_llm_excerpt(segments: Sequence[Mapping[str, Any]]) -> str:
    return build_cue_excerpt(segments)
