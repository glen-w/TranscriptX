"""Appearance date precedence for speaker profile aggregates."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping


def _parse_iso_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    # Accept trailing Z
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def appearance_date_from_sources(
    *,
    transcript_source_imported_at: Any = None,
    sidecar_imported_at: Any = None,
) -> date | None:
    """Frozen appearance date precedence.

    1. Transcript document ``source.imported_at`` if parseable ISO datetime → date
    2. Else import sidecar ``imported_at`` if parseable
    3. Else ``None`` (UI: Unknown date; sort nulls last)

    Do not use filesystem mtime. Do not read nonexistent recording_date /
    session_date fields.
    """
    for candidate in (transcript_source_imported_at, sidecar_imported_at):
        parsed = _parse_iso_datetime(candidate)
        if parsed is not None:
            return parsed.date()
    return None


def appearance_date_from_transcript_document(
    transcript: Mapping[str, Any],
    *,
    sidecar_imported_at: Any = None,
) -> date | None:
    """Extract appearance date using transcript JSON + optional sidecar stamp."""
    source = transcript.get("source")
    source_imported_at = None
    if isinstance(source, Mapping):
        source_imported_at = source.get("imported_at")
    return appearance_date_from_sources(
        transcript_source_imported_at=source_imported_at,
        sidecar_imported_at=sidecar_imported_at,
    )
