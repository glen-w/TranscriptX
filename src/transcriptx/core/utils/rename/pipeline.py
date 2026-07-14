"""Primary managed-rename pipeline, repair, and compatibility wrappers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from transcriptx.core.utils._path_cache import invalidate_path_cache
from transcriptx.core.utils.file_lock import FileLock
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import (
    PROCESSING_STATE_FILE as _DEFAULT_PROCESSING_STATE_FILE,
)
from transcriptx.core.utils.rename.finalize import (
    ArtifactRemapPlan,
    cleanup_abandoned_temps,
    execute_artifact_remap,
    finalize_output_directory_move,
)
from transcriptx.core.utils.rename.journal import (
    JournalLoadError,
    JournalPhase,
    PreparedOpStatus,
    RenameJournalRecord,
    classify_prepared_transaction,
    discover_incomplete_renames,
    journal_dir,
    load_journal,
    managed_rename_lock_path,
    new_operation_id,
    persist_journal,
)
from transcriptx.core.utils.rename.names import (
    RenameNames,
    RenamePaths,
    normalize_base_name,
    validate_target_name,
)
from transcriptx.core.utils.rename.outcome import (
    RenameError,
    RenameManagedOutcome,
    RenameStatus,
    RenameTranscriptOutcome,
    managed_to_legacy,
)
from transcriptx.core.utils.rename.plan import (
    RenameContext,
    RenamePlan,
    build_rename_plan,
)
from transcriptx.core.utils.rename.processing_state import (
    apply_planned_processing_state_update,
)
from transcriptx.core.utils.rename_transaction import RenameTransaction

logger = get_logger()

PROCESSING_STATE_FILE = _DEFAULT_PROCESSING_STATE_FILE


def _processing_state_file() -> Path:
    return Path(PROCESSING_STATE_FILE)


__all__ = [
    "rename_managed_transcript",
    "repair_managed_rename",
    "discover_incomplete_renames",
    "rename_transcript_files_with_outcome",
    "rename_transcript_files",
]


def _safe_persist_journal(record: RenameJournalRecord) -> RenameError | None:
    try:
        persist_journal(record)
        return None
    except Exception as exc:
        logger.error("Failed to persist rename journal: %s", exc)
        return RenameError(
            code="journal_persist_failed",
            message=str(exc),
            phase="journal",
        )


def rename_managed_transcript(
    transcript_path: str | Path,
    raw_target_name: str,
    *,
    dry_run: bool = False,
) -> RenameManagedOutcome:
    """Primary managed-rename entry point."""
    old_transcript = Path(transcript_path)
    ok, err = validate_target_name(
        old_transcript.stem,
        raw_target_name,
        transcript_parent=old_transcript.parent,
    )
    if not ok:
        return RenameManagedOutcome(
            status=RenameStatus.blocked,
            message=err,
            old_transcript_path=str(old_transcript),
            last_error=err,
            errors=[RenameError(code="invalid_target_name", message=err, phase="plan")],
        )

    new_stem = normalize_base_name(raw_target_name)
    new_transcript = old_transcript.parent / f"{new_stem}.json"
    names = RenameNames.from_paths(old_transcript, new_transcript)
    paths = RenamePaths.from_transcripts(old_transcript, new_transcript)

    lock_path = managed_rename_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(lock_path, timeout=60) as lock:
        if not lock.acquired:
            msg = "Could not acquire managed-rename lock"
            return RenameManagedOutcome(
                status=RenameStatus.blocked,
                message=msg,
                last_error=msg,
                old_transcript_path=str(old_transcript),
                new_transcript_path=str(new_transcript),
                errors=[RenameError(code="lock_failed", message=msg, phase="plan")],
            )
        return _run_under_lock(names=names, paths=paths, dry_run=dry_run)


def _staged_json_writes(plan: RenamePlan) -> list[dict]:
    staged_json: list[dict] = []
    for move in plan.sidecar_moves:
        if move.staged_payload is not None:
            staged_json.append(
                {
                    "path": str(move.dest),
                    "payload": move.staged_payload,
                    "description": f"Write import sidecar payload: {move.dest}",
                }
            )
    return staged_json


def _journal_from_plan(
    plan: RenamePlan,
    *,
    operation_id: str,
    names: RenameNames,
    paths: RenamePaths,
    state_file: Path,
    state_snapshot: dict | None,
    warnings: list[str],
    staged_json: list[dict],
) -> RenameJournalRecord:
    """Assemble the prepared-phase journal record from a successful plan."""
    remap_moves = []
    if plan.finalize_plan is not None:
        remap_moves = [
            [str(s), str(d)] for s, d in plan.finalize_plan.artifact_remap.moves
        ]

    return RenameJournalRecord(
        operation_id=operation_id,
        phase=JournalPhase.prepared.value,
        old_transcript_path=str(paths.old_transcript),
        new_transcript_path=str(paths.new_transcript),
        old_output_dir=str(paths.old_output_dir),
        new_output_dir=str(paths.new_output_dir),
        artifact_remap_moves=remap_moves,
        needs_output_dir_move=bool(
            plan.finalize_plan and plan.finalize_plan.needs_output_dir_move
        ),
        old_audio_path=str(plan.planned_old_audio or ""),
        new_audio_path=str(plan.planned_new_audio or ""),
        audio_kind=plan.audio.kind.value if plan.audio else "",
        audio_renamed=plan.audio_renamed,
        warnings=list(warnings),
        names={
            "old_stem": names.old_stem,
            "new_stem": names.new_stem,
            "old_canonical": names.old_canonical,
            "new_canonical": names.new_canonical,
        },
        transaction_file_renames=[
            [str(s), str(d), desc] for s, d, desc in plan.transaction_file_renames
        ],
        staged_json_writes=staged_json,
        processing_state_file=str(state_file),
        processing_state_mutation=(
            plan.state_mutation.to_serializable() if plan.state_mutation else None
        ),
        planned_old_slug=plan.planned_old_slug,
        planned_new_slug=plan.planned_new_slug,
        processing_state_snapshot=state_snapshot,
    )


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
    # Still proceed as committed_partial with the new path.
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


def _run_under_lock(
    *,
    names: RenameNames,
    paths: RenamePaths,
    dry_run: bool,
) -> RenameManagedOutcome:
    operation_id = new_operation_id()
    warnings: list[str] = []
    errors: list[RenameError] = []

    state_file = _processing_state_file()
    state_snapshot = None
    if state_file.exists():
        with open(state_file, "r", encoding="utf-8") as handle:
            state_snapshot = json.load(handle)

    rename_history_at_iso = datetime.now(timezone.utc).isoformat()
    ctx = RenameContext(
        old_name=names.old_stem,
        new_name=names.new_stem,
        transcript_path=str(paths.old_transcript),
        transcript_file=paths.old_transcript,
        new_transcript_path=paths.new_transcript,
        old_output_dir=paths.old_output_dir,
        new_output_dir=paths.new_output_dir,
        names=names,
        paths=paths,
    )
    plan = build_rename_plan(
        ctx,
        state_snapshot,
        rename_history_at_iso,
        processing_state_file=state_file,
    )
    warnings.extend(plan.warnings)

    if plan.blocked:
        return RenameManagedOutcome(
            status=RenameStatus.blocked,
            message=plan.block_message,
            last_error=plan.block_message,
            warnings=warnings,
            old_transcript_path=str(paths.old_transcript),
            new_transcript_path=str(paths.new_transcript),
            planned_ops=tuple(desc for _, _, desc in plan.transaction_file_renames),
            errors=[
                RenameError(
                    code="plan_blocked",
                    message=plan.block_message,
                    phase="plan",
                )
            ],
        )

    staged_json = _staged_json_writes(plan)
    journal = _journal_from_plan(
        plan,
        operation_id=operation_id,
        names=names,
        paths=paths,
        state_file=state_file,
        state_snapshot=state_snapshot,
        warnings=warnings,
        staged_json=staged_json,
    )

    if dry_run:
        return RenameManagedOutcome(
            status=RenameStatus.dry_run,
            message="Dry run: validation and planning succeeded (no domain-state changes)",
            operation_id=None,
            transaction_attempted=True,
            transaction_succeeded=True,
            transaction_committed=False,
            finalize_attempted=False,
            finalize_succeeded=True,
            reconciliation_succeeded=True,
            warnings=warnings,
            old_transcript_path=str(paths.old_transcript),
            new_transcript_path=str(paths.new_transcript),
            old_audio_path=journal.old_audio_path,
            new_audio_path=journal.new_audio_path if plan.audio_renamed else "",
            audio_kind=journal.audio_kind,
            audio_renamed=plan.audio_renamed,
            planned_ops=tuple(desc for _, _, desc in plan.transaction_file_renames)
            + plan.finalize_ops,
            old_slug=plan.planned_old_slug,
            new_slug=plan.planned_new_slug,
        )

    journal_dir().mkdir(parents=True, exist_ok=True)
    prep_err = _safe_persist_journal(journal)
    if prep_err is not None:
        return RenameManagedOutcome(
            status=RenameStatus.blocked,
            message=f"Could not persist rename journal: {prep_err.message}",
            operation_id=operation_id,
            last_error=prep_err.message,
            errors=[prep_err],
            warnings=warnings,
            old_transcript_path=str(paths.old_transcript),
            new_transcript_path=str(paths.new_transcript),
        )

    txn_failure = _execute_rename_transaction(
        plan,
        journal=journal,
        operation_id=operation_id,
        state_file=state_file,
        staged_json=staged_json,
        paths=paths,
        warnings=warnings,
        errors=errors,
    )
    if txn_failure is not None:
        return txn_failure

    # Domain ops committed — non-rollbackable journal marker.
    marker_failure = _mark_transaction_committed(
        journal,
        operation_id=operation_id,
        paths=paths,
        warnings=warnings,
        errors=errors,
    )
    if marker_failure is not None:
        return marker_failure

    return _post_commit_pipeline(
        journal=journal,
        plan=plan,
        names=names,
        paths=paths,
        warnings=warnings,
        errors=errors,
        transaction_attempted=True,
    )


def _run_finalize_phase(
    journal: RenameJournalRecord,
    warnings: list[str],
    errors: list[RenameError],
) -> tuple[bool, bool, bool, bool]:
    """Output-dir move + artifact remap; journal advances to finalized when done.

    Returns (finalize_attempted, finalize_succeeded, output_dir_move_completed,
    artifact_remap_completed). Mutates journal/warnings/errors in place; errors
    appended here downgrade the final journal phase to reconciled.
    """
    finalize_attempted = False
    finalize_succeeded = True
    output_dir_move_completed = journal.output_dir_move_completed
    artifact_remap_completed = journal.artifact_remap_completed

    needs_move = journal.needs_output_dir_move
    remap_moves = [(Path(s), Path(d)) for s, d in journal.artifact_remap_moves]
    if needs_move or remap_moves:
        finalize_attempted = True
        if needs_move and not output_dir_move_completed:
            try:
                status = finalize_output_directory_move(
                    Path(journal.old_output_dir), Path(journal.new_output_dir)
                )
                if status in {"completed", "already_done", "noop"}:
                    output_dir_move_completed = True
                    journal.output_dir_move_completed = True
                elif status == "both_absent":
                    finalize_succeeded = False
                    err = RenameError(
                        code="output_dir_both_absent",
                        message=(
                            f"Both output dirs absent: {journal.old_output_dir} / "
                            f"{journal.new_output_dir}"
                        ),
                        phase="finalize",
                    )
                    errors.append(err)
                    journal.errors.append(
                        {
                            "code": err.code,
                            "message": err.message,
                            "phase": err.phase,
                        }
                    )
            except Exception as e:
                finalize_succeeded = False
                err = RenameError(
                    code="output_dir_move_failed",
                    message=str(e),
                    phase="finalize",
                )
                errors.append(err)
                journal.errors.append(
                    {"code": err.code, "message": err.message, "phase": err.phase}
                )
                warnings.append(
                    "Output directory finalize failed after the rename transaction "
                    "committed; check output folders for a partial merge."
                )

        if remap_moves and not artifact_remap_completed:
            remap_plan = ArtifactRemapPlan(moves=tuple(remap_moves))
            remap_errors = execute_artifact_remap(remap_plan)
            if remap_errors:
                finalize_succeeded = False
                for msg in remap_errors:
                    err = RenameError(
                        code="artifact_remap_failed",
                        message=msg,
                        phase="finalize",
                    )
                    errors.append(err)
                    journal.errors.append(
                        {"code": err.code, "message": err.message, "phase": err.phase}
                    )
            else:
                artifact_remap_completed = True
                journal.artifact_remap_completed = True

    if needs_move or remap_moves:
        if (not needs_move or output_dir_move_completed) and (
            not remap_moves or artifact_remap_completed
        ):
            journal.phase = JournalPhase.finalized.value
        # else remain transaction_committed / prior phase with errors
    else:
        journal.phase = JournalPhase.finalized.value
        output_dir_move_completed = True
        artifact_remap_completed = True
        journal.output_dir_move_completed = True
        journal.artifact_remap_completed = True

    jerr = _safe_persist_journal(journal)
    if jerr is not None:
        errors.append(jerr)

    return (
        finalize_attempted,
        finalize_succeeded,
        output_dir_move_completed,
        artifact_remap_completed,
    )


def _run_reconcile_phase(
    journal: RenameJournalRecord,
    warnings: list[str],
    errors: list[RenameError],
) -> tuple[bool, str | None, str | None]:
    """Slug reconcile + path-cache invalidation + abandoned-temp cleanup.

    Returns (reconciliation_succeeded, old_slug, new_slug). Mutates
    journal/warnings/errors in place.
    """
    old_slug = journal.old_slug or journal.planned_old_slug
    new_slug = journal.new_slug or journal.planned_new_slug
    reconciliation_succeeded = True
    from transcriptx.core.utils.slug_manager import (
        SlugConflictError,
        update_index_after_transcript_rename,
    )

    try:
        old_slug, new_slug = update_index_after_transcript_rename(
            journal.old_transcript_path, journal.new_transcript_path
        )
        journal.old_slug = old_slug
        journal.new_slug = new_slug
    except SlugConflictError as e:
        reconciliation_succeeded = False
        err = RenameError(code="slug_conflict", message=str(e), phase="reconcile")
        errors.append(err)
        journal.errors.append(
            {"code": err.code, "message": err.message, "phase": err.phase}
        )
        warnings.append(f"Slug index reconciliation failed: {e}")
    except Exception as e:
        reconciliation_succeeded = False
        err = RenameError(
            code="slug_reconciliation_failed", message=str(e), phase="reconcile"
        )
        errors.append(err)
        journal.errors.append(
            {"code": err.code, "message": err.message, "phase": err.phase}
        )
        warnings.append(f"Slug index reconciliation failed: {e}")

    try:
        invalidate_path_cache(journal.old_transcript_path)
        invalidate_path_cache(journal.new_transcript_path)
    except Exception as e:
        err = RenameError(
            code="cache_invalidation_failed",
            message=str(e),
            phase="reconcile",
        )
        errors.append(err)
        journal.errors.append(
            {"code": err.code, "message": err.message, "phase": err.phase}
        )
        reconciliation_succeeded = False

    cleanup_abandoned_temps(recorded_temps=journal.recorded_temps)
    return reconciliation_succeeded, old_slug, new_slug


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
    plan: RenamePlan | None,
    names: RenameNames | None,
    paths: RenamePaths,
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
    # Do not clear prior errors — retain history and append a repair attempt.
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
        # Keep prior soft errors in error_history; clear active errors for this attempt.
        record.error_history.extend(prior_errors)
        record.errors = []
        paths = RenamePaths(
            old_transcript=Path(record.old_transcript_path),
            new_transcript=Path(record.new_transcript_path),
            old_output_dir=Path(record.old_output_dir),
            new_output_dir=Path(record.new_output_dir),
        )
        outcome = _post_commit_pipeline(
            journal=record,
            plan=None,
            names=None,
            paths=paths,
            warnings=list(record.warnings),
            errors=[],
            transaction_attempted=True,
        )
        # Annotate latest repair attempt outcome
        if record.repair_attempts:
            record.repair_attempts[-1]["outcome_status"] = outcome.status.value
            record.repair_attempts[-1]["outcome_error_count"] = len(outcome.errors)
            _safe_persist_journal(record)
        return outcome


def rename_transcript_files_with_outcome(
    old_name: str, new_name: str, transcript_path: str, dry_run: bool = False
) -> RenameTranscriptOutcome:
    """Compatibility wrapper: fail closed if old_name mismatches path stem."""
    transcript = Path(transcript_path)
    expected = normalize_base_name(transcript.stem)
    provided = normalize_base_name(old_name)
    if provided != expected:
        msg = (
            f"Compatibility rename rejected: old_name={old_name!r} does not match "
            f"transcript stem {transcript.stem!r}"
        )
        logger.error("%s", msg)
        return RenameTranscriptOutcome(
            transaction_attempted=False,
            transaction_succeeded=False,
            transaction_committed=False,
            finalize_attempted=False,
            finalize_succeeded=False,
            last_error=msg,
            status=RenameStatus.blocked,
            errors=[
                RenameError(code="compat_name_mismatch", message=msg, phase="plan")
            ],
        )
    outcome = rename_managed_transcript(transcript, new_name, dry_run=dry_run)
    return managed_to_legacy(outcome)


def rename_transcript_files(
    old_name: str, new_name: str, transcript_path: str, dry_run: bool = False
) -> bool:
    """Legacy bool wrapper around ``rename_transcript_files_with_outcome``."""
    return rename_transcript_files_with_outcome(
        old_name, new_name, transcript_path, dry_run=dry_run
    ).ok
