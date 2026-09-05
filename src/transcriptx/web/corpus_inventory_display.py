"""UI-only formatting for corpus inventory enums and timestamps."""

from __future__ import annotations

from datetime import datetime, timezone

from transcriptx.app.corpus_inventory.models import (
    AnalysisState,
    AnalysisStatus,
    CorrectionsState,
    CorrectionsStatus,
    InventoryRow,
    SpeakerIdState,
    SpeakerIdStatus,
)
from transcriptx.utils.text_utils import format_duration_display_from_config

_MARK_OK = "✓"
_MARK_EMPTY = "—"


def format_short_date(value: datetime | None) -> str:
    if value is None:
        return _MARK_EMPTY
    return value.strftime("%-d %b") if _platform_supports_minus_d() else value.strftime("%d %b").lstrip("0")


def _platform_supports_minus_d() -> bool:
    try:
        datetime(2026, 8, 12).strftime("%-d")
        return True
    except ValueError:
        return False


def format_relative_age(
    value: datetime | None, *, now: datetime | None = None
) -> str:
    if value is None:
        return _MARK_EMPTY
    current = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    delta = current - value
    seconds = int(delta.total_seconds())
    if seconds < 0:
        seconds = 0
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 48:
        return f"{hours}h ago"
    days = hours // 24
    if days < 14:
        return f"{days}d ago"
    return format_short_date(value)


def format_speaker_id_mark(state: SpeakerIdState) -> str:
    if state.status is SpeakerIdStatus.COMPLETE:
        return _MARK_OK
    if state.status is SpeakerIdStatus.UNKNOWN:
        return "?"
    return _MARK_EMPTY


def format_corrections_mark(state: CorrectionsState) -> str:
    if state.status is CorrectionsStatus.COMPLETE:
        return _MARK_OK
    if state.status is CorrectionsStatus.PENDING:
        pending = state.pending_count
        return str(pending) if pending is not None else "…"
    if state.status is CorrectionsStatus.UNKNOWN:
        return "?"
    return _MARK_EMPTY


def format_analysis_mark(state: AnalysisState) -> str:
    if state.status is AnalysisStatus.UNANALYSED:
        return _MARK_EMPTY
    if state.status is AnalysisStatus.UNKNOWN:
        return "?"
    if state.status is AnalysisStatus.FAILED:
        return "failed"
    succeeded = state.modules_succeeded
    eligible = state.modules_eligible
    if succeeded is None or eligible is None:
        if state.status is AnalysisStatus.COMPLETED:
            return _MARK_OK
        return "…"
    if state.status is AnalysisStatus.COMPLETED and succeeded == eligible:
        return _MARK_OK
    return f"{succeeded}/{eligible}"


def format_speaker_id_label(state: SpeakerIdState) -> str:
    labels = {
        SpeakerIdStatus.COMPLETE: "Complete",
        SpeakerIdStatus.PARTIAL: "Partial",
        SpeakerIdStatus.NONE: "Not started",
        SpeakerIdStatus.UNKNOWN: "Unknown",
    }
    return labels[state.status]


def format_corrections_label(state: CorrectionsState) -> str:
    if state.status is CorrectionsStatus.UNKNOWN:
        return "Unknown"
    if state.status is CorrectionsStatus.NEVER_STARTED:
        return "Not started"
    accepted = state.accepted_count if state.accepted_count is not None else 0
    pending = state.pending_count if state.pending_count is not None else 0
    return f"{accepted} accepted · {pending} unresolved"


def format_analysis_label(state: AnalysisState) -> str:
    if state.status is AnalysisStatus.UNANALYSED:
        return "Not started"
    if state.status is AnalysisStatus.UNKNOWN:
        return "Unknown"
    if state.status is AnalysisStatus.FAILED:
        if state.modules_succeeded is not None and state.modules_eligible is not None:
            return f"Failed ({state.modules_succeeded}/{state.modules_eligible} modules)"
        return "Failed"
    if state.modules_succeeded is not None and state.modules_eligible is not None:
        return f"{state.modules_succeeded}/{state.modules_eligible} modules complete"
    if state.status is AnalysisStatus.COMPLETED:
        return "Complete"
    return "Incomplete"


def inventory_table_row(row: InventoryRow, *, include_path: bool = False) -> dict[str, str]:
    data = {
        "Transcript": row.title,
        "Date": format_short_date(row.imported_at),
        "Duration": format_duration_display_from_config(row.duration_seconds),
        "Speakers": "—" if row.speaker_count is None else str(row.speaker_count),
        "Speaker ID": format_speaker_id_mark(row.speaker),
        "Corrections": format_corrections_mark(row.corrections),
        "Analysis": format_analysis_mark(row.analysis),
        "Tags": ", ".join(row.tags) if row.tags else "—",
        "Last activity": format_relative_age(row.last_activity_at),
    }
    if include_path:
        data["Path"] = str(row.transcript_path)
    return data
