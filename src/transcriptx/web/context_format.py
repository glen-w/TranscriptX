"""Pure subject/run context formatting for the Streamlit GUI.

No Streamlit or HTML — presentation controls live in ``components/run_id_info``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

_CANONICAL_SUBJECT_TYPES = frozenset({"transcript", "group"})


@dataclass(frozen=True)
class ContextPresentation:
    """Human-readable context line plus raw run id for the info control."""

    primary_text: str
    raw_run_id: str | None
    tooltip_label: str


def _clean_label(value: Any) -> str | None:
    """Strip surrounding whitespace; ignore empty candidates. Preserve Unicode."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def friendly_subject_label(
    subject_type: str | None,
    *,
    subject_id: str | None = None,
    slug_labels: Mapping[str, str] | None = None,
    display_name: str | None = None,
    stem: str | None = None,
) -> str:
    """Resolve a human-readable subject label for canonical subject types.

    Transcript precedence: slug-index basename → display name → stem → subject_id.
    Group precedence: display name → subject_id.
    Unknown subject_type → ``No subject``.
    """
    if subject_type not in _CANONICAL_SUBJECT_TYPES:
        return "No subject"

    cleaned_id = _clean_label(subject_id)
    cleaned_display = _clean_label(display_name)
    cleaned_stem = _clean_label(stem)

    if subject_type == "transcript":
        if cleaned_id and slug_labels:
            from_index = _clean_label(slug_labels.get(cleaned_id))
            if from_index:
                return from_index
        if cleaned_display:
            return cleaned_display
        if cleaned_stem:
            return cleaned_stem
        if cleaned_id:
            return cleaned_id
        return "No transcript"

    # group
    if cleaned_display:
        return cleaned_display
    if cleaned_id:
        return cleaned_id
    return "No group"


def parse_run_timestamp(run_id: str | None) -> datetime | None:
    """Parse a leading ``YYYYMMDD_HHMMSS`` prefix from a run id.

    Uses the same naive datetime semantics as the former Overview helper.
    Never raises; returns ``None`` for malformed/empty/unsupported input.
    """
    if run_id is None:
        return None
    try:
        text = str(run_id).strip()
        if not text or "_" not in text:
            return None
        parts = text.split("_")
        if len(parts) < 2:
            return None
        date_time_str = f"{parts[0]}_{parts[1]}"
        return datetime.strptime(date_time_str, "%Y%m%d_%H%M%S")
    except (ValueError, TypeError, IndexError, AttributeError):
        return None


def _format_human_run_dt(dt: datetime) -> str:
    """Format like ``Run 13 Jul 2026, 03:29`` (portable; no %-d)."""
    return f"Run {dt.day} {dt.strftime('%b %Y, %H:%M')}"


def format_run_display(
    run_id: str | None,
    fallback_dt: datetime | None = None,
    *,
    allow_raw_fallback: bool = False,
) -> str:
    """Format a run for display.

    When ``allow_raw_fallback`` is False (context bar / Recent Runs):
    parsed timestamp → fallback_dt → ``Run selected`` → ``No run``.

    When True (Overview may use this):
    parsed timestamp → fallback_dt → raw run_id → ``No run``.
    """
    parsed = parse_run_timestamp(run_id)
    if parsed is not None:
        return _format_human_run_dt(parsed)

    if isinstance(fallback_dt, datetime):
        return _format_human_run_dt(fallback_dt)

    cleaned = _clean_label(run_id)
    if cleaned:
        if allow_raw_fallback:
            return cleaned
        return "Run selected"
    return "No run"


_EMPTY_SUBJECT_LABELS = frozenset({"No transcript", "No group", "No subject"})


def format_context_line(
    *,
    subject_type: str | None,
    subject_label: str,
    run_id: str | None = None,
    fallback_dt: datetime | None = None,
) -> ContextPresentation:
    """Build primary context text without repeating Transcript/Group tokens.

    When nothing is selected (empty subject and no run), primary text is blank.
    """
    cleaned_label = _clean_label(subject_label)
    label = cleaned_label or (
        "No transcript"
        if subject_type == "transcript"
        else "No group" if subject_type == "group" else "No subject"
    )
    run_display = format_run_display(
        run_id, fallback_dt=fallback_dt, allow_raw_fallback=False
    )
    subject_empty = label in _EMPTY_SUBJECT_LABELS
    run_empty = run_display == "No run"
    primary = "" if subject_empty and run_empty else f"{label} / {run_display}"
    raw = _clean_label(run_id)
    tooltip = (
        f"Full run identifier: {raw}" if raw else "Full run identifier unavailable"
    )
    return ContextPresentation(
        primary_text=primary,
        raw_run_id=raw,
        tooltip_label=tooltip,
    )
