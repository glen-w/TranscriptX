"""Filter, sort, and Home ranking over InventoryRow (no I/O)."""

from __future__ import annotations

from transcriptx.app.corpus_inventory.models import (
    AnalysisStatus,
    ContinueAction,
    CorrectionsStatus,
    InventoryRow,
    LibraryFilter,
    LibrarySort,
    LibraryWorkflowPreset,
    SpeakerIdStatus,
)


def row_matches_preset(row: InventoryRow, preset: LibraryWorkflowPreset) -> bool:
    if preset is LibraryWorkflowPreset.ALL:
        return True
    if preset is LibraryWorkflowPreset.UNANALYSED:
        return row.analysis.status is AnalysisStatus.UNANALYSED
    if preset is LibraryWorkflowPreset.NEEDS_SPEAKER_ID:
        return row.speaker.status in {SpeakerIdStatus.NONE, SpeakerIdStatus.PARTIAL}
    if preset is LibraryWorkflowPreset.CORRECTIONS_PENDING:
        return row.corrections.status is CorrectionsStatus.PENDING
    if preset is LibraryWorkflowPreset.ANALYSED:
        return row.analysis.status is AnalysisStatus.COMPLETED
    if preset is LibraryWorkflowPreset.FAILED_INCOMPLETE:
        return row.analysis.status in {AnalysisStatus.FAILED, AnalysisStatus.INCOMPLETE}
    return True


def row_matches_query(row: InventoryRow, query: str) -> bool:
    needle = (query or "").strip().casefold()
    if not needle:
        return True
    haystacks = [
        row.title,
        row.transcript_path.stem,
        row.transcript_path.name,
        row.slug or "",
    ]
    return any(needle in item.casefold() for item in haystacks if item)


def apply_library_filter(
    rows: list[InventoryRow], library_filter: LibraryFilter
) -> list[InventoryRow]:
    matched = [
        row
        for row in rows
        if row_matches_preset(row, library_filter.preset)
        and row_matches_query(row, library_filter.query)
        and (
            not library_filter.source_id
            or row.source_id == library_filter.source_id
        )
    ]
    return sort_inventory_rows(matched, library_filter.sort)


def _analysis_completion_key(row: InventoryRow) -> tuple[int, float]:
    eligible = row.analysis.modules_eligible
    succeeded = row.analysis.modules_succeeded
    if not eligible or succeeded is None:
        return (1, 0.0)
    return (0, -(succeeded / eligible))


def sort_inventory_rows(
    rows: list[InventoryRow], sort: LibrarySort
) -> list[InventoryRow]:
    if sort is LibrarySort.NAME:
        return sorted(rows, key=lambda row: (row.title.casefold(), str(row.transcript_path)))
    if sort is LibrarySort.DURATION:
        return sorted(
            rows,
            key=lambda row: (
                row.duration_seconds is None,
                -(row.duration_seconds or 0.0),
                row.title.casefold(),
            ),
        )
    if sort is LibrarySort.ANALYSIS_COMPLETION:
        return sorted(
            rows,
            key=lambda row: (*_analysis_completion_key(row), row.title.casefold()),
        )
    if sort is LibrarySort.RECENTLY_ADDED:
        return sorted(
            rows,
            key=lambda row: (
                row.imported_at is None,
                -(row.imported_at.timestamp() if row.imported_at else 0.0),
                row.title.casefold(),
            ),
        )
    # RECENTLY_WORKED
    return sorted(
        rows,
        key=lambda row: (
            row.last_activity_at is None,
            -(row.last_activity_at.timestamp() if row.last_activity_at else 0.0),
            row.title.casefold(),
        ),
    )


def continue_working_priority(row: InventoryRow) -> tuple[int, float, str]:
    """Lower tuple sorts first. Resumable work beats recency."""
    if row.corrections.status is CorrectionsStatus.PENDING:
        priority = 0
    elif row.speaker.status is SpeakerIdStatus.PARTIAL:
        priority = 1
    elif row.speaker.status is SpeakerIdStatus.NONE and (row.speaker_count or 0) > 0:
        priority = 2
    elif row.analysis.status in {AnalysisStatus.INCOMPLETE, AnalysisStatus.FAILED}:
        priority = 3
    else:
        priority = 4
    recency = -(row.last_activity_at.timestamp() if row.last_activity_at else 0.0)
    return (priority, recency, row.title.casefold())


def continue_working_action(row: InventoryRow) -> ContinueAction:
    priority, _, _ = continue_working_priority(row)
    if priority == 0:
        return ContinueAction.CORRECTIONS
    if priority in {1, 2}:
        return ContinueAction.SPEAKER_ID
    if priority == 3:
        return ContinueAction.ANALYSE
    return ContinueAction.OPEN


def select_continue_working(
    rows: list[InventoryRow], *, limit: int = 5
) -> list[InventoryRow]:
    ranked = sorted(rows, key=continue_working_priority)
    resumable = [
        row for row in ranked if continue_working_priority(row)[0] < 4
    ]
    chosen: list[InventoryRow] = []
    seen: set[str] = set()
    for row in resumable:
        key = str(row.transcript_path)
        if key in seen:
            continue
        seen.add(key)
        chosen.append(row)
        if len(chosen) >= limit:
            return chosen
    for row in ranked:
        key = str(row.transcript_path)
        if key in seen:
            continue
        seen.add(key)
        chosen.append(row)
        if len(chosen) >= limit:
            break
    return chosen


def needs_attention_counts(rows: list[InventoryRow]) -> dict[str, int]:
    return {
        "speaker_id": sum(
            1
            for row in rows
            if row.speaker.status in {SpeakerIdStatus.NONE, SpeakerIdStatus.PARTIAL}
        ),
        "analysis": sum(
            1
            for row in rows
            if row.analysis.status in {AnalysisStatus.INCOMPLETE, AnalysisStatus.FAILED}
        ),
        "corrections": sum(
            1 for row in rows if row.corrections.status is CorrectionsStatus.PENDING
        ),
    }


def corpus_summary(rows: list[InventoryRow]) -> dict[str, int | float]:
    analysed = sum(1 for row in rows if row.analysis.status is AnalysisStatus.COMPLETED)
    duration = sum(
        row.duration_seconds or 0.0
        for row in rows
        if row.duration_seconds is not None
    )
    return {
        "transcript_count": len(rows),
        "analysed_count": analysed,
        "total_duration_seconds": duration,
    }
