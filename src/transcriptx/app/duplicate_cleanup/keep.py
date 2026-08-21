"""Pick the richest library copy in a duplicate group."""

from __future__ import annotations

from transcriptx.app.corpus_inventory.models import (
    AnalysisStatus,
    CorrectionsStatus,
    InventoryRow,
    SpeakerIdStatus,
)
from transcriptx.app.duplicate_cleanup.models import DuplicateMember, MemberRole


def _analysis_rank(row: InventoryRow) -> tuple[int, float]:
    status = row.analysis.status
    if status is AnalysisStatus.COMPLETED:
        rank = 3
    elif status is AnalysisStatus.INCOMPLETE:
        rank = 2
    elif status is AnalysisStatus.FAILED:
        rank = 1
    else:
        rank = 0
    eligible = row.analysis.modules_eligible
    succeeded = row.analysis.modules_succeeded
    if eligible and succeeded is not None:
        return rank, succeeded / max(eligible, 1)
    return rank, 0.0


def richness_score(
    member: DuplicateMember,
    rows: dict[str, InventoryRow],
) -> tuple:
    """Higher tuples win. Path is omitted; callers use it only as a tiebreak."""
    path = member.fingerprint.path
    resolved = str(path)
    try:
        resolved = str(path.expanduser().resolve())
    except OSError:
        pass
    row = rows.get(resolved) or rows.get(str(path))
    mtime = member.fingerprint.mtime_ns
    if row is None:
        return (
            1 if member.role is MemberRole.TRANSCRIPT else 0,
            0,
            0.0,
            0,
            0,
            0,
            float(mtime),
            0.0,
        )
    status = row.analysis.status
    if status is AnalysisStatus.COMPLETED:
        analysis_rank = 3
    elif status is AnalysisStatus.INCOMPLETE:
        analysis_rank = 2
    elif status is AnalysisStatus.FAILED:
        analysis_rank = 1
    else:
        analysis_rank = 0
    ratio = 0.0
    eligible = row.analysis.modules_eligible
    succeeded = row.analysis.modules_succeeded
    if eligible and succeeded is not None:
        ratio = succeeded / max(eligible, 1)
    corr_complete = 1 if row.corrections.status is CorrectionsStatus.COMPLETE else 0
    corr_accepted = row.corrections.accepted_count or 0
    speaker_rank = {
        SpeakerIdStatus.COMPLETE: 3,
        SpeakerIdStatus.PARTIAL: 2,
        SpeakerIdStatus.UNKNOWN: 1,
        SpeakerIdStatus.NONE: 0,
    }[row.speaker.status]
    imported = row.imported_at.timestamp() if row.imported_at else 0.0
    activity = row.last_activity_at.timestamp() if row.last_activity_at else 0.0
    return (
        1 if member.role is MemberRole.TRANSCRIPT else 0,
        analysis_rank,
        ratio,
        corr_complete,
        corr_accepted,
        speaker_rank,
        activity,
        imported,
    )


def pick_keeper(
    members: list[DuplicateMember],
    rows: dict[str, InventoryRow],
) -> DuplicateMember:
    if not members:
        raise ValueError("Cannot pick a keeper from an empty group")
    best_score = max(richness_score(member, rows) for member in members)
    tied = [
        member for member in members if richness_score(member, rows) == best_score
    ]
    return min(tied, key=lambda member: str(member.fingerprint.path))
