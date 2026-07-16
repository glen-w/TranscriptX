"""Primary managed-rename pipeline coordinator and compatibility wrappers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from transcriptx.core.utils.file_lock import FileLock
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import (
    PROCESSING_STATE_FILE as _DEFAULT_PROCESSING_STATE_FILE,
)
from transcriptx.core.utils.rename.journal import (
    _safe_persist_journal,
    discover_incomplete_renames,
    journal_dir,
    managed_rename_lock_path,
    new_operation_id,
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
from transcriptx.core.utils.rename.post_commit import (
    _post_commit_pipeline,
)
from transcriptx.core.utils.rename.repair import repair_managed_rename
from transcriptx.core.utils.rename.transaction_phase import (
    _execute_rename_transaction,
    _mark_transaction_committed,
)

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
    state_snapshot,
    warnings: list[str],
    staged_json: list[dict],
):
    from transcriptx.core.utils.rename.journal import (
        JournalPhase,
        RenameJournalRecord,
    )

    artifact_remap_moves: list[list[str]] = []
    if plan.finalize_plan is not None:
        artifact_remap_moves = [
            [str(s), str(d)] for s, d in plan.finalize_plan.artifact_remap.moves
        ]
    return RenameJournalRecord(
        operation_id=operation_id,
        phase=JournalPhase.prepared.value,
        old_transcript_path=str(paths.old_transcript),
        new_transcript_path=str(paths.new_transcript),
        old_output_dir=str(paths.old_output_dir),
        new_output_dir=str(paths.new_output_dir),
        artifact_remap_moves=artifact_remap_moves,
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
        staged_json_writes=list(staged_json),
        processing_state_file=str(state_file),
        processing_state_mutation=(
            plan.state_mutation.to_serializable() if plan.state_mutation else None
        ),
        planned_old_slug=plan.planned_old_slug,
        planned_new_slug=plan.planned_new_slug,
        processing_state_snapshot=state_snapshot,
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
        warnings=warnings,
        errors=errors,
        transaction_attempted=True,
    )


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
