"""Crash-safe recovery classification and read gating for speaker profile ops."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from transcriptx.core.speaker_profiles.errors import RepairRequiredError
from transcriptx.core.speaker_profiles.hashing import sha256_file
from transcriptx.core.speaker_profiles.models import (
    OperationPlanActionV1,
    SpeakerProfileOperationV1,
)
from transcriptx.core.speaker_profiles.store_io import (
    load_operation,
    utc_now_iso,
    write_bytes_under_root,
    write_operation,
)

PathState = Literal[
    "absent",
    "matches_before",
    "matches_after",
    "corrupt_or_other",
]

# Phases that block intersecting profile/link reads until resolved.
BLOCKING_PHASES = frozenset(
    {
        "prepared",
        "staged",
        "transaction_committed",
        "finalized",
        "needs_repair",
        "failed",
    }
)

PROVEN_ABORTED = "proven_aborted"


@dataclass(frozen=True)
class ActionClassification:
    """Hash-based classification of one planned action's on-disk outcome."""

    path: str
    action: str
    state: PathState
    actual_sha256: str | None


@dataclass(frozen=True)
class OperationRecoveryReport:
    operation_id: str
    phase: str
    classifications: tuple[ActionClassification, ...]
    recovery_class: Literal[
        "complete",
        "proven_aborted",
        "partial",
        "ambiguous",
        "needs_repair",
    ]
    blocking: bool


def list_operations(root: Path) -> list[SpeakerProfileOperationV1]:
    """Parseable operations only (corrupt files omitted — see list_operations_detailed)."""
    return list(list_operations_detailed(root).operations)


@dataclass(frozen=True)
class OperationsListResult:
    operations: tuple[SpeakerProfileOperationV1, ...]
    corrupt_paths: tuple[str, ...]


def list_operations_detailed(root: Path) -> OperationsListResult:
    """List operations and surface corrupt ``.op.json`` paths (fail-closed)."""
    ops_dir = Path(root) / "operations"
    if not ops_dir.is_dir():
        return OperationsListResult(operations=(), corrupt_paths=())
    out: list[SpeakerProfileOperationV1] = []
    corrupt: list[str] = []
    for path in sorted(ops_dir.glob("*.op.json")):
        try:
            out.append(load_operation(path))
        except Exception:
            corrupt.append(str(path))
    return OperationsListResult(operations=tuple(out), corrupt_paths=tuple(corrupt))


def classify_action(root: Path, action: OperationPlanActionV1) -> ActionClassification:
    """Classify a plan action against live bytes (old/new/absent/other)."""
    target = Path(root) / action.path
    actual = sha256_file(target)
    if actual is None:
        state: PathState = "absent"
    elif action.action == "write" and actual == action.after_sha256:
        state = "matches_after"
    elif (
        action.expected_before_sha256 is not None
        and actual == action.expected_before_sha256
    ):
        state = "matches_before"
    elif action.action == "delete" and action.expected_before_sha256 is None:
        state = "corrupt_or_other"
    else:
        state = "corrupt_or_other"
    return ActionClassification(
        path=action.path,
        action=action.action,
        state=state,
        actual_sha256=actual,
    )


def classify_operation(
    root: Path, op: SpeakerProfileOperationV1
) -> OperationRecoveryReport:
    """Derive recovery class from phase + per-action hash classification."""
    # Terminal non-blocking phases: skip hashing action files.
    if op.phase == "complete":
        return OperationRecoveryReport(
            operation_id=op.operation_id,
            phase=op.phase,
            classifications=(),
            recovery_class="complete",
            blocking=False,
        )

    receipt = op.receipt or {}
    if op.phase == "failed" and receipt.get("abort_class") == PROVEN_ABORTED:
        return OperationRecoveryReport(
            operation_id=op.operation_id,
            phase=op.phase,
            classifications=(),
            recovery_class="proven_aborted",
            blocking=False,
        )

    classes = tuple(classify_action(root, a) for a in op.plan.actions)

    if not classes:
        # Never-started empty plan — treat as proven abort candidate.
        recovery: Literal[
            "complete", "proven_aborted", "partial", "ambiguous", "needs_repair"
        ] = "proven_aborted"
        return OperationRecoveryReport(
            operation_id=op.operation_id,
            phase=op.phase,
            classifications=classes,
            recovery_class=recovery,
            blocking=op.phase in BLOCKING_PHASES and recovery != "proven_aborted",
        )

    if op.phase == "needs_repair":
        return OperationRecoveryReport(
            operation_id=op.operation_id,
            phase=op.phase,
            classifications=classes,
            recovery_class="needs_repair",
            blocking=True,
        )

    # All actions still at before-state (or write targets still absent with
    # expected_before null) ⇒ never applied / clean rollback candidate.
    never_applied = all(_is_before_or_unapplied(c, op) for c in classes)
    if never_applied and op.phase in {"prepared", "staged", "failed"}:
        return OperationRecoveryReport(
            operation_id=op.operation_id,
            phase=op.phase,
            classifications=classes,
            recovery_class="proven_aborted",
            blocking=op.phase != "failed"
            or (op.receipt or {}).get("abort_class") != PROVEN_ABORTED,
        )

    # All actions at after-state ⇒ transactionally applied; may only need finalize.
    fully_applied = all(_is_after_applied(c) for c in classes)
    if fully_applied and op.phase in {
        "staged",
        "transaction_committed",
        "finalized",
    }:
        return OperationRecoveryReport(
            operation_id=op.operation_id,
            phase=op.phase,
            classifications=classes,
            recovery_class="complete",
            blocking=True,  # until marked complete
        )

    # Mix of before/after/other ⇒ partial or ambiguous.
    states = {c.state for c in classes}
    if "corrupt_or_other" in states:
        recovery_class: Literal[
            "complete", "proven_aborted", "partial", "ambiguous", "needs_repair"
        ] = "ambiguous"
    else:
        recovery_class = "partial"

    return OperationRecoveryReport(
        operation_id=op.operation_id,
        phase=op.phase,
        classifications=classes,
        recovery_class=recovery_class,
        blocking=True,
    )


def _is_before_or_unapplied(
    c: ActionClassification, op: SpeakerProfileOperationV1
) -> bool:
    if c.action == "write":
        # Write never applied: absent (new file) or still matches before.
        return c.state in {"absent", "matches_before"}
    # delete never applied: file still present with before hash
    return c.state == "matches_before"


def _is_after_applied(c: ActionClassification) -> bool:
    if c.action == "write":
        return c.state == "matches_after"
    return c.state == "absent"


def affected_relpaths(op: SpeakerProfileOperationV1) -> set[str]:
    return {a.path for a in op.plan.actions}


def blocking_operations_index(
    root: Path,
) -> dict[str, list[SpeakerProfileOperationV1]]:
    """Map relative paths to ops that currently block reads of that path.

    Lists operations once and skips hash classification for terminal
    non-blocking phases (``complete`` / proven-aborted ``failed``).
    """
    index: dict[str, list[SpeakerProfileOperationV1]] = {}
    for op in list_operations(root):
        if op.phase == "complete":
            continue
        receipt = op.receipt or {}
        if op.phase == "failed" and receipt.get("abort_class") == PROVEN_ABORTED:
            continue
        report = classify_operation(root, op)
        if not report.blocking:
            continue
        for relpath in affected_relpaths(op):
            index.setdefault(relpath, []).append(op)
    return index


def blocking_operations_for_path(
    root: Path, relpath: str
) -> list[SpeakerProfileOperationV1]:
    """Return ops that currently block reads of ``relpath``."""
    return list(blocking_operations_index(root).get(relpath, ()))


def assert_relpath_readable(root: Path, relpath: str) -> None:
    """Raise RepairRequiredError when an incomplete op intersects ``relpath``."""
    blockers = blocking_operations_for_path(root, relpath)
    if blockers:
        ids = ", ".join(o.operation_id for o in blockers)
        raise RepairRequiredError(
            f"reads blocked for {relpath}: intersecting operation(s) {ids} "
            f"require repair or proven abort"
        )


def mark_proven_aborted(
    root: Path, op: SpeakerProfileOperationV1, *, reason: str
) -> SpeakerProfileOperationV1:
    """Mark an op failed with proven-aborted receipt (unblocks reads).

    Only valid when classification says never-applied / proven_aborted candidate.
    Does not delete staging/backup of needs_repair ops from other paths.
    """
    report = classify_operation(root, op)
    if report.recovery_class not in {"proven_aborted"} and not all(
        _is_before_or_unapplied(c, op) for c in report.classifications
    ):
        raise RepairRequiredError(
            f"cannot proven-abort operation {op.operation_id}: "
            f"recovery_class={report.recovery_class}"
        )
    receipt = dict(op.receipt or {})
    receipt.update(
        {
            "abort_class": PROVEN_ABORTED,
            "aborted_at": utc_now_iso(),
            "reason": reason,
            "operation_idempotency_key": op.operation_idempotency_key,
        }
    )
    updated = op.model_copy(update={"phase": "failed", "receipt": receipt})
    write_operation(updated, root=root)
    # Safe to strip staging/backup only after proven abort (no domain change).
    _cleanup_op_workdir(root, op.operation_id)
    return updated


def finalize_fully_applied(
    root: Path, op: SpeakerProfileOperationV1
) -> SpeakerProfileOperationV1:
    """Mark a fully-applied incomplete op as complete and strip workdirs."""
    report = classify_operation(root, op)
    if not all(_is_after_applied(c) for c in report.classifications):
        raise RepairRequiredError(
            f"cannot finalize operation {op.operation_id}: not fully applied"
        )
    receipt = dict(op.receipt or {})
    receipt.setdefault("completed_at", utc_now_iso())
    receipt.setdefault("operation_idempotency_key", op.operation_idempotency_key)
    receipt["recovered"] = True
    updated = op.model_copy(update={"phase": "complete", "receipt": receipt})
    write_operation(updated, root=root)
    _cleanup_op_workdir(root, op.operation_id)
    return updated


def rollback_partial_to_before(
    root: Path, op: SpeakerProfileOperationV1
) -> SpeakerProfileOperationV1:
    """Restore before-images from backup for applied actions, then proven-abort.

    Requires backup files for every delete/write that left after-state.
    """
    for action in op.plan.actions:
        classification = classify_action(root, action)
        target = Path(root) / action.path
        if action.action == "write" and classification.state == "matches_after":
            if action.expected_before_sha256 is None:
                # New file: delete after-image.
                if target.exists():
                    target.unlink()
                    from transcriptx.core.speaker_profiles.store_io import fsync_parent

                    fsync_parent(target)
            else:
                if not action.backup_relpath:
                    raise RepairRequiredError(
                        f"missing before-image backup for rollback: {action.path}"
                    )
                backup_path = Path(root) / action.backup_relpath
                if not backup_path.is_file():
                    raise RepairRequiredError(
                        f"missing before-image backup for rollback: {action.backup_relpath}"
                    )
                write_bytes_under_root(target, backup_path.read_bytes(), root=root)
        elif action.action == "delete" and classification.state == "absent":
            assert action.backup_relpath is not None
            backup_path = Path(root) / action.backup_relpath
            if not backup_path.is_file():
                raise RepairRequiredError(
                    f"missing before-image backup for rollback: {action.backup_relpath}"
                )
            write_bytes_under_root(target, backup_path.read_bytes(), root=root)

    # Re-classify then mark proven aborted.
    refreshed = load_operation(
        Path(root) / "operations" / f"{op.operation_id}.op.json"
    )
    return mark_proven_aborted(
        root, refreshed, reason="rolled_back_partial_to_before"
    )


def recover_operation(root: Path, operation_id: str) -> OperationRecoveryReport:
    """Classify and, when safe, auto-complete or proven-abort an operation."""
    path = Path(root) / "operations" / f"{operation_id}.op.json"
    op = load_operation(path)
    report = classify_operation(root, op)

    if report.recovery_class == "complete" and op.phase != "complete":
        if all(_is_after_applied(c) for c in report.classifications):
            finalize_fully_applied(root, op)
            op = load_operation(path)
            return classify_operation(root, op)

    if report.recovery_class == "proven_aborted" and (
        op.phase != "failed"
        or (op.receipt or {}).get("abort_class") != PROVEN_ABORTED
    ):
        mark_proven_aborted(root, op, reason="recovery_never_applied")
        op = load_operation(path)
        return classify_operation(root, op)

    return report


def retention_allows_cleanup(op: SpeakerProfileOperationV1) -> bool:
    """True only when staging/backup bytes may be deleted."""
    if op.phase == "complete":
        return True
    if op.phase == "failed" and (op.receipt or {}).get("abort_class") == PROVEN_ABORTED:
        return True
    return False


def _cleanup_op_workdir(root: Path, operation_id: str) -> None:
    import shutil

    op_dir = Path(root) / "operations" / operation_id
    if op_dir.is_dir():
        shutil.rmtree(op_dir, ignore_errors=True)
