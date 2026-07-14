"""Status enum and structured outcome types for managed rename."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class RenameStatus(str, Enum):
    blocked = "blocked"
    dry_run = "dry_run"
    failed_rolled_back = "failed_rolled_back"
    failed_rollback_incomplete = "failed_rollback_incomplete"
    committed_complete = "committed_complete"
    committed_partial = "committed_partial"


@dataclass(frozen=True)
class RenameError:
    """One structured error (multi-error aggregation across phases)."""

    code: str
    message: str
    phase: str = ""


@dataclass(frozen=True)
class RenameManagedOutcome:
    """Primary result of ``rename_managed_transcript`` / repair."""

    status: RenameStatus
    message: str = ""
    operation_id: str | None = None
    transaction_committed: bool = False
    transaction_attempted: bool = False
    transaction_succeeded: bool = False
    finalize_attempted: bool = False
    finalize_succeeded: bool = False
    output_dir_move_completed: bool = False
    artifact_remap_completed: bool = False
    reconciliation_succeeded: bool = False
    old_transcript_path: str = ""
    new_transcript_path: str = ""
    old_audio_path: str = ""
    new_audio_path: str = ""
    audio_kind: str = ""
    audio_renamed: bool = False
    old_slug: str | None = None
    new_slug: str | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[RenameError] = field(default_factory=list)
    last_error: Optional[str] = None
    planned_ops: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status in {RenameStatus.committed_complete, RenameStatus.dry_run}

    @property
    def partial_success_after_transaction(self) -> bool:
        return (
            self.status == RenameStatus.committed_partial and self.transaction_committed
        )


@dataclass(frozen=True)
class RenameTranscriptOutcome:
    """Legacy compatibility outcome (maps from RenameManagedOutcome)."""

    transaction_attempted: bool
    transaction_succeeded: bool
    transaction_committed: bool
    finalize_attempted: bool
    finalize_succeeded: bool
    warnings: list[str] = field(default_factory=list)
    last_error: Optional[str] = None
    status: RenameStatus | None = None
    operation_id: str | None = None
    errors: list[RenameError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.transaction_succeeded and self.finalize_succeeded

    @property
    def partial_success_after_transaction(self) -> bool:
        return self.transaction_committed and not self.finalize_succeeded


def managed_to_legacy(outcome: RenameManagedOutcome) -> RenameTranscriptOutcome:
    return RenameTranscriptOutcome(
        transaction_attempted=outcome.transaction_attempted,
        transaction_succeeded=outcome.transaction_succeeded,
        transaction_committed=outcome.transaction_committed,
        finalize_attempted=outcome.finalize_attempted,
        finalize_succeeded=outcome.finalize_succeeded,
        warnings=list(outcome.warnings),
        last_error=outcome.last_error,
        status=outcome.status,
        operation_id=outcome.operation_id,
        errors=list(outcome.errors),
    )


def outcome_to_dict(outcome: RenameManagedOutcome) -> dict[str, Any]:
    return {
        "status": outcome.status.value,
        "message": outcome.message,
        "operation_id": outcome.operation_id,
        "transaction_committed": outcome.transaction_committed,
        "old_transcript_path": outcome.old_transcript_path,
        "new_transcript_path": outcome.new_transcript_path,
        "errors": [
            {"code": e.code, "message": e.message, "phase": e.phase}
            for e in outcome.errors
        ],
        "warnings": list(outcome.warnings),
    }
