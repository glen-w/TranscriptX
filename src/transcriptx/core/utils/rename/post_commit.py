"""Post-commit orchestration: finalize + reconcile + journal close."""

from __future__ import annotations

from transcriptx.core.utils.rename.finalize_phase import _run_finalize_phase
from transcriptx.core.utils.rename.journal import (
    JournalPhase,
    RenameJournalRecord,
    _safe_persist_journal,
)
from transcriptx.core.utils.rename.outcome import (
    RenameError,
    RenameManagedOutcome,
    RenameStatus,
)
from transcriptx.core.utils.rename.reconcile import _run_reconcile_phase


def _close_journal_and_build_outcome(
    journal: RenameJournalRecord,
    *,
    operation_id: str,
    transaction_attempted: bool,
    finalize_attempted: bool,
    finalize_succeeded: bool,
    output_dir_move_completed: bool,
    artifact_remap_completed: bool,
    reconciliation_succeeded: bool,
    old_slug: str | None,
    new_slug: str | None,
    warnings: list[str],
    errors: list[RenameError],
) -> RenameManagedOutcome:
    """Close journal (reconciled vs complete) and build the final outcome."""
    if errors:
        journal.phase = JournalPhase.reconciled.value
        journal.warnings = warnings
        journal.error_history.extend(
            [
                {"code": e.code, "message": e.message, "phase": e.phase}
                for e in errors
                if {"code": e.code, "message": e.message, "phase": e.phase}
                not in journal.error_history
            ]
        )
        jerr = _safe_persist_journal(journal)
        if jerr is not None and jerr not in errors:
            errors.append(jerr)
        status = RenameStatus.committed_partial
        message = (
            "Transcript rename committed, but post-commit reconciliation is incomplete. "
            f"Repair with operation_id={operation_id}."
        )
    else:
        journal.phase = JournalPhase.complete.value
        journal.warnings = warnings
        jerr = _safe_persist_journal(journal)
        if jerr is not None:
            errors.append(jerr)
            status = RenameStatus.committed_partial
            message = (
                "Rename finished on disk, but the complete journal marker could not "
                f"be persisted. operation_id={operation_id}."
            )
        else:
            status = RenameStatus.committed_complete
            message = "Renamed managed transcript successfully."

    return RenameManagedOutcome(
        status=status,
        message=message,
        operation_id=operation_id,
        transaction_committed=True,
        transaction_attempted=transaction_attempted,
        transaction_succeeded=True,
        finalize_attempted=finalize_attempted,
        finalize_succeeded=finalize_succeeded
        and not any(e.phase == "finalize" for e in errors),
        output_dir_move_completed=output_dir_move_completed,
        artifact_remap_completed=artifact_remap_completed,
        reconciliation_succeeded=reconciliation_succeeded
        and not any(e.phase == "reconcile" for e in errors),
        warnings=warnings,
        errors=errors,
        last_error=errors[-1].message if errors else None,
        old_transcript_path=journal.old_transcript_path,
        new_transcript_path=journal.new_transcript_path,
        old_audio_path=journal.old_audio_path,
        new_audio_path=journal.new_audio_path if journal.audio_renamed else "",
        audio_kind=journal.audio_kind,
        audio_renamed=journal.audio_renamed,
        old_slug=old_slug,
        new_slug=new_slug,
    )


def _post_commit_pipeline(
    *,
    journal: RenameJournalRecord,
    warnings: list[str],
    errors: list[RenameError],
    transaction_attempted: bool,
) -> RenameManagedOutcome:
    """Finalize + reconcile + close journal (also used journal-only by repair)."""
    operation_id = journal.operation_id

    (
        finalize_attempted,
        finalize_succeeded,
        output_dir_move_completed,
        artifact_remap_completed,
    ) = _run_finalize_phase(journal, warnings, errors)

    reconciliation_succeeded, old_slug, new_slug = _run_reconcile_phase(
        journal, warnings, errors
    )

    return _close_journal_and_build_outcome(
        journal,
        operation_id=operation_id,
        transaction_attempted=transaction_attempted,
        finalize_attempted=finalize_attempted,
        finalize_succeeded=finalize_succeeded,
        output_dir_move_completed=output_dir_move_completed,
        artifact_remap_completed=artifact_remap_completed,
        reconciliation_succeeded=reconciliation_succeeded,
        old_slug=old_slug,
        new_slug=new_slug,
        warnings=warnings,
        errors=errors,
    )
