"""Finalize phase coordination (output-dir move + artifact remap + journal)."""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.utils.rename.finalize import (
    ArtifactRemapPlan,
    execute_artifact_remap,
    finalize_output_directory_move,
)
from transcriptx.core.utils.rename.journal import (
    JournalPhase,
    RenameJournalRecord,
    _safe_persist_journal,
)
from transcriptx.core.utils.rename.outcome import RenameError


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
