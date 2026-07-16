"""Repair incomplete managed renames from durable journal records."""

from __future__ import annotations

from datetime import datetime, timezone

from transcriptx.core.utils.file_lock import FileLock
from transcriptx.core.utils.rename.journal import (
    JournalLoadError,
    JournalPhase,
    PreparedOpStatus,
    classify_prepared_transaction,
    load_journal,
    managed_rename_lock_path,
    _safe_persist_journal,
)
from transcriptx.core.utils.rename.outcome import (
    RenameError,
    RenameManagedOutcome,
    RenameStatus,
)
from transcriptx.core.utils.rename.post_commit import _post_commit_pipeline


def repair_managed_rename(operation_id: str) -> RenameManagedOutcome:
    """Resume finalization and reconciliation from a durable journal record."""
    try:
        record = load_journal(operation_id)
    except JournalLoadError as exc:
        return RenameManagedOutcome(
            status=RenameStatus.blocked,
            message=str(exc),
            last_error=str(exc),
            operation_id=operation_id,
            errors=[
                RenameError(
                    code="invalid_operation_id", message=str(exc), phase="journal"
                )
            ],
        )
    if record is None:
        return RenameManagedOutcome(
            status=RenameStatus.blocked,
            message=f"Unknown rename operation_id: {operation_id}",
            last_error="journal not found",
            operation_id=operation_id,
        )
    if record.phase == JournalPhase.complete.value:
        return RenameManagedOutcome(
            status=RenameStatus.committed_complete,
            message="Rename operation already complete",
            operation_id=operation_id,
            transaction_committed=True,
            transaction_succeeded=True,
            transaction_attempted=True,
            finalize_succeeded=True,
            output_dir_move_completed=True,
            artifact_remap_completed=True,
            reconciliation_succeeded=True,
            old_transcript_path=record.old_transcript_path,
            new_transcript_path=record.new_transcript_path,
            old_audio_path=record.old_audio_path,
            new_audio_path=record.new_audio_path if record.audio_renamed else "",
            audio_kind=record.audio_kind,
            audio_renamed=record.audio_renamed,
            old_slug=record.old_slug,
            new_slug=record.new_slug,
        )

    now = datetime.now(timezone.utc).isoformat()
    record.repair_attempt_count = int(record.repair_attempt_count or 0) + 1
    record.last_repair_at = now
    prior_errors = list(record.errors)
    record.repair_attempts.append(
        {
            "at": now,
            "attempt": record.repair_attempt_count,
            "from_phase": record.phase,
            "prior_error_count": len(prior_errors),
        }
    )

    if record.phase == JournalPhase.prepared.value:
        classification = classify_prepared_transaction(record)
        if classification == PreparedOpStatus.fully_committed:
            record.phase = JournalPhase.transaction_committed.value
            _safe_persist_journal(record)
        elif classification == PreparedOpStatus.not_started:
            return RenameManagedOutcome(
                status=RenameStatus.blocked,
                message=(
                    "Rename journal is in prepared phase and no transaction ops "
                    "started; safe to discard or retry a fresh rename."
                ),
                operation_id=operation_id,
                last_error="prepared_not_started",
                old_transcript_path=record.old_transcript_path,
                new_transcript_path=record.new_transcript_path,
                errors=[
                    RenameError(
                        code="prepared_not_started",
                        message="Transaction never started",
                        phase="journal",
                    )
                ],
            )
        else:
            return RenameManagedOutcome(
                status=RenameStatus.blocked,
                message=(
                    f"Rename journal prepared-phase classification is "
                    f"{classification.value}; manual inspection required."
                ),
                operation_id=operation_id,
                last_error="prepared_ambiguous",
                old_transcript_path=record.old_transcript_path,
                new_transcript_path=record.new_transcript_path,
                errors=[
                    RenameError(
                        code="prepared_phase_unrecoverable",
                        message=classification.value,
                        phase="journal",
                    )
                ],
            )

    lock_path = managed_rename_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(lock_path, timeout=60) as lock:
        if not lock.acquired:
            return RenameManagedOutcome(
                status=RenameStatus.blocked,
                message="Could not acquire managed-rename lock for repair",
                operation_id=operation_id,
                last_error="lock failed",
            )
        record.error_history.extend(prior_errors)
        record.errors = []
        outcome = _post_commit_pipeline(
            journal=record,
            warnings=list(record.warnings),
            errors=[],
            transaction_attempted=True,
        )
        if record.repair_attempts:
            record.repair_attempts[-1]["outcome_status"] = outcome.status.value
            record.repair_attempts[-1]["outcome_error_count"] = len(outcome.errors)
            _safe_persist_journal(record)
        return outcome
