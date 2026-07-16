"""Rename transaction phase: execute domain txn + committed journal marker."""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.utils.rename.journal import (
    JournalPhase,
    RenameJournalRecord,
    _safe_persist_journal,
)
from transcriptx.core.utils.rename.names import RenamePaths
from transcriptx.core.utils.rename.outcome import (
    RenameError,
    RenameManagedOutcome,
    RenameStatus,
)
from transcriptx.core.utils.rename.plan import RenamePlan
from transcriptx.core.utils.rename.processing_state import (
    apply_planned_processing_state_update,
)
from transcriptx.core.utils.rename_transaction import RenameTransaction


def _execute_rename_transaction(
    plan: RenamePlan,
    *,
    journal: RenameJournalRecord,
    operation_id: str,
    state_file: Path,
    staged_json: list[dict],
    paths: RenamePaths,
    warnings: list[str],
    errors: list[RenameError],
) -> RenameManagedOutcome | None:
    """Execute the rename transaction; returns a failure outcome or None on success."""
    transaction = RenameTransaction(
        processing_state_file=state_file,
        dry_run=False,
    )
    for src, dest, desc in plan.transaction_file_renames:
        transaction.add_rename(src, dest, desc)
    if plan.staged_state_write is not None:
        sw = plan.staged_state_write
        transaction.add_state_update(
            apply_planned_processing_state_update,
            state_snapshot=sw.state_snapshot,
            mutation=sw.mutation,
            state_file=Path(sw.state_file),
        )
    for write in staged_json:
        transaction.add_json_write(
            Path(write["path"]),
            write["payload"],
            description=write.get("description", ""),
        )

    txn_result = transaction.execute()
    if txn_result.ok:
        return None

    journal.phase = JournalPhase.prepared.value
    primary = RenameError(
        code=txn_result.failure_code or "transaction_failed",
        message=txn_result.failure_message or "rename transaction failed",
        phase="transaction",
    )
    errors.append(primary)
    journal.errors.append(
        {"code": primary.code, "message": primary.message, "phase": primary.phase}
    )
    if txn_result.rollback is not None:
        for rb_err in txn_result.rollback.errors:
            err = RenameError(
                code="rollback_failed",
                message=rb_err,
                phase="rollback",
            )
            errors.append(err)
            journal.errors.append(
                {"code": err.code, "message": err.message, "phase": err.phase}
            )
    journal.error_history.extend(journal.errors)
    _safe_persist_journal(journal)

    if txn_result.rollback is not None and not txn_result.rollback.ok:
        status = RenameStatus.failed_rollback_incomplete
        message = (
            "Rename transaction failed and rollback did not fully complete. "
            "Manual repair may be required."
        )
    else:
        status = RenameStatus.failed_rolled_back
        message = (
            f"Rename transaction failed; changes rolled back "
            f"({primary.code}: {primary.message})"
        )
    return RenameManagedOutcome(
        status=status,
        message=message,
        operation_id=operation_id,
        transaction_attempted=True,
        transaction_succeeded=False,
        transaction_committed=False,
        warnings=warnings,
        last_error=primary.message,
        old_transcript_path=str(paths.old_transcript),
        new_transcript_path=str(paths.new_transcript),
        errors=errors,
    )


def _mark_transaction_committed(
    journal: RenameJournalRecord,
    *,
    operation_id: str,
    paths: RenamePaths,
    warnings: list[str],
    errors: list[RenameError],
) -> RenameManagedOutcome | None:
    """Persist the non-rollbackable transaction_committed journal marker.

    Returns a committed_partial outcome if the marker cannot be persisted,
    else None.
    """
    journal.phase = JournalPhase.transaction_committed.value
    jerr = _safe_persist_journal(journal)
    if jerr is None:
        return None
    errors.append(jerr)
    journal.errors.append(
        {"code": jerr.code, "message": jerr.message, "phase": jerr.phase}
    )
    journal.error_history.append(
        {"code": jerr.code, "message": jerr.message, "phase": jerr.phase}
    )
    return RenameManagedOutcome(
        status=RenameStatus.committed_partial,
        message=(
            "Transcript rename committed on disk, but the transaction_committed "
            f"journal marker could not be persisted. operation_id={operation_id}"
        ),
        operation_id=operation_id,
        transaction_committed=True,
        transaction_attempted=True,
        transaction_succeeded=True,
        warnings=warnings,
        errors=errors,
        last_error=jerr.message,
        old_transcript_path=str(paths.old_transcript),
        new_transcript_path=str(paths.new_transcript),
        old_audio_path=journal.old_audio_path,
        new_audio_path=journal.new_audio_path if journal.audio_renamed else "",
        audio_kind=journal.audio_kind,
        audio_renamed=journal.audio_renamed,
    )
