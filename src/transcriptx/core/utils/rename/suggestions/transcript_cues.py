"""Deterministic date/title/public-event cues from transcript text."""

from __future__ import annotations

import re
from calendar import month_abbr, month_name
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from transcriptx.core.utils.rename.suggestions.models import RawRenameCue
from transcriptx.core.utils.rename.title_stem import (
    split_title_tokens,
    stem_looks_like_natural_language_title,
)

_MONTHS = "|".join(
    sorted(
        {m.lower() for m in list(month_name)[1:] + list(month_abbr)[1:] if m},
        key=len,
        reverse=True,
    )
)
_RE_ISO = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
_RE_MONTH_DAY_YEAR = re.compile(
    rf"\b({_MONTHS})\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(20\d{{2}})\b",
    re.IGNORECASE,
)
_RE_DAY_MONTH_YEAR = re.compile(
    rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTHS})\s+(20\d{{2}})\b",
    re.IGNORECASE,
)
_RE_RECORDED_ON = re.compile(
    r"(?:recorded|aired|published|held)\s+on\s+"
    r"(20\d{2}-\d{2}-\d{2}|"
    rf"{_RE_MONTH_DAY_YEAR.pattern}|"
    rf"{_RE_DAY_MONTH_YEAR.pattern})",
    re.IGNORECASE,
)
_RE_WELCOME_EVENT_ON = re.compile(
    r"\bwelcome\s+to\s+(?:(?:the|this|our)\s+)?(webinar|webcast)\s+on\b",
    re.IGNORECASE,
)
_RE_THIS_EVENT_ON = re.compile(
    r"\bthis\s+(webinar|webcast)\s+is\s+on\b",
    re.IGNORECASE,
)
_RE_WELCOME_TITLE = re.compile(
    r"(?:welcome to|this (?:webinar|webcast|session) (?:is|on)|today(?:'s)? (?:webinar|session) (?:is|on))\s+"
    r"([A-Z0-9][^.!?\n]{4,80})",
    re.IGNORECASE,
)
_PUBLIC_FILENAME_MARKERS = re.compile(
    r"zoom|webex|teams|gotowebinar|streamyard|webinar|webcast|youtube|gmt\d",
    re.IGNORECASE,
)
_TITLE_STOPWORDS = frozenset({"a", "an", "the", "of", "and", "or", "in", "on", "for", "to"})
_MIN_NL_TITLE_TOKENS = 4
_PUBLIC_TRANSCRIPT_MARKERS = re.compile(
    r"thanks for joining|welcome to the (?:webinar|webcast)|this session is being recorded",
    re.IGNORECASE,
)
_WEBINAR_LINE_MARKERS = re.compile(
    r"webinar|webcast|recorded on|aired on|published on|welcome to",
    re.IGNORECASE,
)


def _segment_text(segment: Mapping[str, Any]) -> str:
    return str(segment.get("text") or segment.get("transcript") or "").strip()


def _month_to_int(name: str) -> int | None:
    low = name.strip().lower()[:3]
    for i, abbr in enumerate(month_abbr):
        if i == 0:
            continue
        if abbr and abbr.lower() == low:
            return i
    for i, full in enumerate(month_name):
        if i == 0:
            continue
        if full and full.lower() == name.strip().lower():
            return i
    return None


def _safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def parse_date_from_text(text: str) -> tuple[date | None, str]:
    """Return (date, quote) from the first strong date phrase in ``text``."""
    if not text:
        return None, ""
    for match in _RE_RECORDED_ON.finditer(text):
        quote = match.group(0)[:160]
        inner = match.group(0)
        iso = _RE_ISO.search(inner)
        if iso:
            y, mo, d = int(iso.group(1)), int(iso.group(2)), int(iso.group(3))
            parsed = _safe_date(y, mo, d)
            if parsed:
                return parsed, quote
        mdy = _RE_MONTH_DAY_YEAR.search(inner)
        if mdy:
            mo = _month_to_int(mdy.group(1))
            if mo:
                parsed = _safe_date(int(mdy.group(3)), mo, int(mdy.group(2)))
                if parsed:
                    return parsed, quote
        dmy = _RE_DAY_MONTH_YEAR.search(inner)
        if dmy:
            mo = _month_to_int(dmy.group(2))
            if mo:
                parsed = _safe_date(int(dmy.group(3)), mo, int(dmy.group(1)))
                if parsed:
                    return parsed, quote
    iso = _RE_ISO.search(text)
    if iso:
        y, mo, d = int(iso.group(1)), int(iso.group(2)), int(iso.group(3))
        parsed = _safe_date(y, mo, d)
        if parsed:
            return parsed, iso.group(0)
    mdy = _RE_MONTH_DAY_YEAR.search(text)
    if mdy:
        mo = _month_to_int(mdy.group(1))
        if mo:
            parsed = _safe_date(int(mdy.group(3)), mo, int(mdy.group(2)))
            if parsed:
                return parsed, mdy.group(0)[:160]
    dmy = _RE_DAY_MONTH_YEAR.search(text)
    if dmy:
        mo = _month_to_int(dmy.group(2))
        if mo:
            parsed = _safe_date(int(dmy.group(3)), mo, int(dmy.group(1)))
            if parsed:
                return parsed, dmy.group(0)[:160]
    return None, ""


def _moderator_event_type_keyword(text: str) -> str:
    """Return ``webinar`` / ``webcast`` for stock moderator intros, not the topic clause."""
    if not text:
        return ""
    for pattern in (_RE_WELCOME_EVENT_ON, _RE_THIS_EVENT_ON):
        match = pattern.search(text)
        if match:
            return match.group(1).lower()
    filler = re.compile(
        r"^(?:our|the|this)\s+(webinar|webcast)\s+on\b",
        re.IGNORECASE,
    )
    welcome = _RE_WELCOME_TITLE.search(text)
    if welcome:
        tail = welcome.group(1).strip(" .,:;\"'")
        m = filler.match(tail)
        if m:
            return m.group(1).lower()
    return ""


def extract_title_from_text(text: str) -> str:
    """Heuristic short title from transcript excerpt."""
    if not text:
        return ""
    event_kw = _moderator_event_type_keyword(text)
    if event_kw:
        return event_kw
    match = _RE_WELCOME_TITLE.search(text)
    if match:
        title = match.group(1).strip(" .,:;\"'")
        if len(title) >= 4:
            return title
    for line in text.splitlines()[:12]:
        line = line.strip()
        if not line or len(line) < 8 or len(line) > 100:
            continue
        if line.lower().startswith(("hello", "hi ", "thanks", "good morning")):
            continue
        if _PUBLIC_TRANSCRIPT_MARKERS.search(line):
            continue
        return line
    return ""


def _stem_qualifies_for_web_lookup(stem: str) -> bool:
    if not stem_looks_like_natural_language_title(stem):
        return False
    tokens = [
        t
        for t in split_title_tokens(stem)
        if t.lower() not in _TITLE_STOPWORDS
    ]
    return len(tokens) >= _MIN_NL_TITLE_TOKENS


def looks_like_public_event(filename: str, segments: Sequence[Mapping[str, Any]]) -> bool:
    name = filename or ""
    if _PUBLIC_FILENAME_MARKERS.search(name):
        return True
    blob = " ".join(_segment_text(s) for s in segments[:40])
    if _PUBLIC_TRANSCRIPT_MARKERS.search(blob):
        return True
    stem = Path(name).stem if name else ""
    return _stem_qualifies_for_web_lookup(stem)


def build_cue_excerpt(segments: Sequence[Mapping[str, Any]], *, max_lines: int = 80) -> str:
    lines: list[str] = []
    for segment in segments[:max_lines]:
        text = _segment_text(segment)
        if text:
            lines.append(text)
    extra: list[str] = []
    for segment in segments[max_lines:]:
        text = _segment_text(segment)
        if text and _WEBINAR_LINE_MARKERS.search(text):
            extra.append(text)
            if len(extra) >= 20:
                break
    return "\n".join(lines + extra)


def extract_transcript_cues(
    segments: Sequence[Mapping[str, Any]],
) -> list[RawRenameCue]:
    excerpt = build_cue_excerpt(segments)
    cues: list[RawRenameCue] = []
    event_date, quote = parse_date_from_text(excerpt)
    if event_date is not None:
        cues.append(
            RawRenameCue(
                basis="transcript_date",
                confidence="strong",
                detail="Date phrase in transcript",
                event_date=event_date,
                quote=quote,
                _priority=1,
            )
        )
    title = extract_title_from_text(excerpt)
    if title:
        cues.append(
            RawRenameCue(
                basis="transcript_title",
                confidence="likely",
                detail="Title cue from transcript",
                title=title,
                _priority=3,
            )
        )
    return cues


def transcript_source_mtime(transcript_path: str) -> datetime | None:
    """Read ``source.file_mtime`` from transcript JSON when present."""
    from pathlib import Path

    import json

    path = Path(transcript_path)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    source = raw.get("source")
    if not isinstance(source, dict):
        return None
    mtime = source.get("file_mtime")
    if isinstance(mtime, (int, float)) and mtime > 0:
        return datetime.fromtimestamp(float(mtime))
    imported = source.get("imported_at")
    if isinstance(imported, str) and imported.strip():
        try:
            return datetime.fromisoformat(imported.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None
