"""Transcript viewer chapters panel (topic_shift coverage spans)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from transcriptx.core.analysis.topic_shift.visibility import (
    resolve_topic_shift_visibility,
    topic_shift_enrichment_path,
    topic_shift_spans_path,
)
from transcriptx.utils.text_utils import format_duration_display_from_config

CHAPTER_PENDING_KEY = "transcript_viewer_chapter_pending"
CHAPTER_JUMP_KEY = "transcript_viewer_chapter_jump"
TRANSCRIPT_TAB_KEY = "transcript_viewer_tab"
TRANSCRIPT_TAB_CONTROL_KEY = "transcript_viewer_tab_control"

_TAB_LABELS = {
    "turns": "Turns",
    "segments": "Segments",
    "chapters": "Chapters",
}


@dataclass(frozen=True)
class ChapterRow:
    span_id: str
    index: int
    title: str
    time_start: float
    time_end: float
    viewer_target_source_index: int | None
    leading_boundary_id: str | None
    strength: float | None
    summary: str | None


def _deterministic_display_label(span: dict[str, Any]) -> str:
    """Viewer-facing fallback when LLM titles / keyword hints are absent."""
    raw = str(span.get("label") or "").strip()
    idx = span.get("index", 0)
    try:
        chapter_n = int(idx) + 1
    except (TypeError, ValueError):
        chapter_n = 1
    if raw.startswith("Segment "):
        return f"Chapter {raw[len('Segment ') :]}"
    if raw:
        return raw
    return f"Chapter {chapter_n}"


def _title_from_keyword_hints(hints: object) -> str | None:
    if not isinstance(hints, list):
        return None
    parts: list[str] = []
    for hint in hints:
        tok = str(hint or "").strip()
        if not tok:
            continue
        parts.append(tok[:1].upper() + tok[1:] if len(tok) > 1 else tok.upper())
        if len(parts) >= 4:
            break
    if not parts:
        return None
    return " · ".join(parts)


def _title_for_span(
    span: dict[str, Any],
    *,
    enrichment: dict[str, Any] | None,
) -> tuple[str, str | None]:
    sid = str(span.get("span_id") or "")
    det_label = _deterministic_display_label(span)
    summary = None
    if enrichment:
        ui_mode = enrichment.get("ui_mode") or "chapter_titles"
        if ui_mode == "overall_summary":
            overall = enrichment.get("overall_summary")
            hint_title = _title_from_keyword_hints(span.get("keyword_hints"))
            return hint_title or det_label, (str(overall) if overall else None)
        for entry in enrichment.get("entries") or []:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("span_id") or "") != sid:
                continue
            title = entry.get("title")
            if title and str(title).strip():
                return str(title).strip(), (
                    str(entry.get("summary")).strip() if entry.get("summary") else None
                )
            break
    hint_title = _title_from_keyword_hints(span.get("keyword_hints"))
    if hint_title:
        return hint_title, summary
    return det_label, summary


def load_chapter_rows(run_root: Path | None) -> list[ChapterRow]:
    if run_root is None:
        return []
    visibility = resolve_topic_shift_visibility(run_root)
    if visibility != "show":
        return []
    spans_path = topic_shift_spans_path(run_root)
    try:
        spans_raw = json.loads(spans_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(spans_raw, dict):
        return []
    spans = list(spans_raw.get("coverage_spans") or [])
    enrichment = None
    enrich_path = topic_shift_enrichment_path(run_root)
    if enrich_path.is_file():
        try:
            enrichment = json.loads(enrich_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            enrichment = None
    # Suppress enrichment titles when outcome skipped with only fallbacks is fine;
    # dual-ACTIVE: if enrichment outcome exists but deterministic show — use merge.
    if isinstance(enrichment, dict) and enrichment.get("outcome") == "skipped":
        # Still allow overall_summary UI mode caption; titles fall back.
        pass

    rows: list[ChapterRow] = []
    events_by_id: dict[str, float] = {}
    # Strength only via leading_boundary_id — look up from events envelope if present
    events_path = (
        Path(run_root) / "topic_shift" / "data" / "global" / "topic_shift.events.json"
    )
    if events_path.is_file():
        try:
            ev_raw = json.loads(events_path.read_text(encoding="utf-8"))
            for ev in (ev_raw or {}).get("events") or []:
                if not isinstance(ev, dict):
                    continue
                eid = str(ev.get("event_id") or "")
                strength = None
                evid = ev.get("evidence")
                if isinstance(evid, list):
                    for item in evid:
                        if isinstance(item, dict) and "normalized_strength" in item:
                            try:
                                strength = float(item["normalized_strength"])
                            except (TypeError, ValueError):
                                strength = None
                            break
                elif isinstance(evid, dict) and "normalized_strength" in evid:
                    try:
                        strength = float(evid["normalized_strength"])
                    except (TypeError, ValueError):
                        strength = None
                if eid and strength is not None:
                    events_by_id[eid] = strength
        except (OSError, ValueError, TypeError):
            pass

    for span in spans:
        if not isinstance(span, dict):
            continue
        title, summary = _title_for_span(span, enrichment=enrichment)
        lead = span.get("leading_boundary_id")
        strength = events_by_id.get(str(lead)) if lead else None
        target = span.get("viewer_target_source_index")
        rows.append(
            ChapterRow(
                span_id=str(span.get("span_id") or ""),
                index=int(span.get("index") or 0),
                title=title,
                time_start=float(span.get("time_start") or 0.0),
                time_end=float(span.get("time_end") or 0.0),
                viewer_target_source_index=(
                    int(target) if isinstance(target, int) else None
                ),
                leading_boundary_id=str(lead) if lead else None,
                strength=strength,
                summary=summary,
            )
        )
    return rows


def sticky_chapter_jump(session_state: dict[str, Any]) -> int | None:
    value = session_state.get(CHAPTER_JUMP_KEY)
    return int(value) if type(value) is int else None


def clear_chapter_jump(session_state: dict[str, Any]) -> None:
    session_state[CHAPTER_JUMP_KEY] = None


def queue_chapter_jump(
    session_state: dict[str, Any],
    *,
    source_index: int,
    play: bool = True,
) -> None:
    """Queue chapter navigation: switch to Segments, filter, optional play."""
    idx = int(source_index)
    session_state[CHAPTER_PENDING_KEY] = {
        "jump_index": idx,
        "play": bool(play),
    }
    session_state[CHAPTER_JUMP_KEY] = idx
    # Programmatic tab switch (widget key must match label option).
    session_state[TRANSCRIPT_TAB_KEY] = "segments"
    session_state[TRANSCRIPT_TAB_CONTROL_KEY] = _TAB_LABELS["segments"]
    # Search wins over jump in filtered_display_segments — clear it.
    session_state["transcript_search"] = ""


def consume_chapter_pending(
    session_state: dict[str, Any],
) -> dict[str, Any] | None:
    pending = session_state.get(CHAPTER_PENDING_KEY)
    if not isinstance(pending, dict):
        return None
    session_state[CHAPTER_PENDING_KEY] = None
    return pending


def format_chapter_time_range(start: float, end: float) -> str:
    a = format_duration_display_from_config(start)
    b = format_duration_display_from_config(end)
    return f"{a} – {b}"
