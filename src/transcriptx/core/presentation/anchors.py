"""
Formatting helpers for segment anchors in Markdown outputs.
"""

from __future__ import annotations

from typing import Iterable, List, Optional

from transcriptx.utils.text_utils import format_time


def format_timecode(t: float | None) -> str:
    if t is None:
        return "--"
    try:
        return format_time(float(t))
    except (TypeError, ValueError):
        return "--"


def _first_and_count(values: Iterable) -> tuple[Optional[str], int]:
    normalized: List[str] = []
    for value in values or []:
        if value is None:
            continue
        normalized.append(str(value))
    if not normalized:
        return None, 0
    return normalized[0], len(normalized)


def _format_segment_index(indexes: Optional[Iterable[int]]) -> Optional[str]:
    if not indexes:
        return None
    try:
        ints = [int(v) for v in indexes if v is not None]
    except (TypeError, ValueError):
        return None
    if not ints:
        return None
    if len(ints) == 1:
        return f"seg#{ints[0]}"
    return f"seg#{min(ints)}-{max(ints)}"


def _format_segment_id(
    segment_indexes: Optional[Iterable[int]],
    segment_db_ids: Optional[Iterable[int]],
    segment_uuids: Optional[Iterable[str]],
) -> Optional[str]:
    index_part = _format_segment_index(segment_indexes)
    if index_part:
        return index_part

    first_db, count_db = _first_and_count(segment_db_ids or [])
    if first_db:
        suffix = f"+{count_db - 1}" if count_db > 1 else ""
        return f"db#{first_db}{suffix}"

    first_uuid, count_uuid = _first_and_count(segment_uuids or [])
    if first_uuid:
        short_uuid = str(first_uuid)[:8]
        suffix = f"+{count_uuid - 1}" if count_uuid > 1 else ""
        return f"uuid#{short_uuid}{suffix}"
    return None


def format_segment_anchor(
    *,
    start: float | None = None,
    end: float | None = None,
    speaker: str | None = None,
    segment_indexes: Optional[Iterable[int]] = None,
    segment_db_ids: Optional[Iterable[int]] = None,
    segment_uuids: Optional[Iterable[str]] = None,
) -> str:
    start_text = format_timecode(start)
    end_text = format_timecode(end)
    if start_text != "--" or end_text != "--":
        time_part = (
            start_text if end_text == "--" else f"{start_text}-{end_text}"
        )
    else:
        time_part = "--"

    parts = [time_part]
    if speaker:
        parts.append(str(speaker))
    segment_id = _format_segment_id(segment_indexes, segment_db_ids, segment_uuids)
    if segment_id:
        parts.append(segment_id)
    return " | ".join(parts)


def format_segment_anchor_md(**kwargs: object) -> str:
    anchor = format_segment_anchor(**kwargs)
    return f"[{anchor}]"
