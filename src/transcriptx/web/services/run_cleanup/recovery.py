"""Pending-journal reconciliation and retry sequencing — Phase A extract."""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.run_writer_locks import (
    RunWriterLock,
    try_per_run_lock,
    try_run_tree_mutation_gate,
)
from transcriptx.web.services.run_cleanup import deletion_phase
from transcriptx.web.services.run_cleanup import fd_ops
from transcriptx.web.services.run_cleanup import finalization
from transcriptx.web.services.run_cleanup import journal
from transcriptx.web.services.run_cleanup import journal_ops
from transcriptx.web.services.run_cleanup import locking
from transcriptx.web.services.run_cleanup import results as results_mod
from transcriptx.web.services.run_cleanup.models import (
    CLEANUP_BUSY,
    CLEANUP_POLICY_VERSION,
    JOURNAL_SCHEMA_VERSION,
    CleanupMode,
    CleanupResult,
    CleanupStatus,
    CleanupTarget,
    CleanupTargetResult,
    EntryClassification,
    SubjectType,
    TargetStatus,
)
from transcriptx.web.services.run_cleanup.path_helpers import (
    output_root_for_target,
    validate_roots,
)

_JOURNAL_STATE_TO_TARGET_STATUS: dict[str, TargetStatus] = {
    "physical_deleted": TargetStatus.PHYSICAL_DELETED,
    "external_disappeared": TargetStatus.EXTERNAL_DISAPPEARED,
    "physical_delete_refused": TargetStatus.PHYSICAL_DELETE_REFUSED,
    "physical_delete_partial": TargetStatus.PHYSICAL_DELETE_PARTIAL,
    "physical_delete_failed": TargetStatus.PHYSICAL_DELETE_FAILED,
    "locked_skip": TargetStatus.LOCKED_SKIP,
    "staging_failed": TargetStatus.STAGING_FAILED,
    "planned": TargetStatus.SKIPPED,
    "staging_started": TargetStatus.SKIPPED,
    "staged": TargetStatus.SKIPPED,
}


def _target_result_from_journal_row(row: dict) -> CleanupTargetResult | None:
    """Rebuild a target result; refuse to fabricate non-positive filesystem ids."""
    try:
        subject_type = SubjectType(str(row["subject_type"]))
        subject_id = str(row["subject_id"])
        run_id = str(row["run_id"])
        canonical_path = str(row["canonical_path"])
        root_relative_path = str(row.get("root_relative_path") or "")
        filesystem_dev = int(row["filesystem_dev"])
        filesystem_ino = int(row["filesystem_ino"])
    except (KeyError, TypeError, ValueError):
        return None
    if filesystem_dev <= 0 or filesystem_ino <= 0:
        return None
    state = str(row.get("state") or "")
    status = _JOURNAL_STATE_TO_TARGET_STATUS.get(state, TargetStatus.SKIPPED)
    return CleanupTargetResult(
        subject_type=subject_type,
        subject_id=subject_id,
        run_id=run_id,
        root_relative_path=root_relative_path,
        canonical_path=canonical_path,
        status=status,
        message=str(row.get("error") or state or "terminal journal row"),
        staging_path=str(row["staging_path"]) if row.get("staging_path") else None,
        filesystem_dev=filesystem_dev,
        filesystem_ino=filesystem_ino,
        root_kind=subject_type,
    )


def _synthesize_terminal_result(
    *,
    operation_id: str,
    plan_id: str,
    mode: CleanupMode,
    data: dict,
) -> CleanupResult:
    """Deterministic ALREADY_EXECUTED reconstruction from a terminal journal."""
    rows = list(data.get("targets") or [])
    derived = results_mod.status_from_journal_targets(rows)
    warnings = ["Operation already terminal"]
    if str(data.get("status") or "") and str(data.get("status")) != derived.value:
        warnings.append(
            f"journal operation status {data.get('status')!r} differs from "
            f"target-vector status {derived.value!r}; using target vector"
        )
    rebuilt: list[CleanupTargetResult] = []
    malformed = 0
    for row in rows:
        if not isinstance(row, dict):
            malformed += 1
            continue
        tr = _target_result_from_journal_row(row)
        if tr is None:
            malformed += 1
            continue
        rebuilt.append(tr)
    if malformed:
        warnings.append(
            f"{malformed} journal target row(s) could not be reconstructed safely"
        )
    deleted = sum(1 for t in rows if str(t.get("state") or "") == "physical_deleted")
    return CleanupResult(
        operation_id=operation_id,
        plan_id=plan_id,
        mode=mode,
        status=CleanupStatus.ALREADY_EXECUTED,
        targets=tuple(rebuilt),
        warnings=tuple(warnings),
        errors=(),
        visible_removed_count=deleted,
        physically_deleted_count=deleted,
    )


logger = get_logger()


def reconcile_planned_or_started_target(
    host,
    *,
    operation_id: str,
    target_row: dict,
    fake: CleanupTarget,
    staging_path: Path,
) -> CleanupTargetResult | None:
    """FS-reconcile planned/staging_started. Returns result if handled, else None to delete."""
    source_present = fd_ops.lexists(fake.canonical_path)
    staging_present = fd_ops.lexists(staging_path)
    if staging_present and not source_present:
        # Orphaned staged tree — recover identity then allow physical delete.
        try:
            st = fd_ops.lstat_nofollow(staging_path)
            if (
                int(st.st_dev) == fake.filesystem_dev
                and int(st.st_ino) == fake.filesystem_ino
            ):
                journal_ops.persist_target_state(
                    host,
                    operation_id,
                    canonical_path=fake.canonical_path,
                    state="recovered_from_incomplete_stage",
                    staging_path=str(staging_path),
                    staged_dev=int(st.st_dev),
                    staged_ino=int(st.st_ino),
                )
                return None  # proceed to physical delete
        except OSError as exc:
            return deletion_phase.refused_result(
                fake,
                f"cannot reconcile staged remnant: {exc}",
                staging_path=staging_path,
            )
        return deletion_phase.refused_result(
            fake,
            "staging present but identity does not match journal",
            staging_path=staging_path,
        )
    if staging_present and source_present:
        return deletion_phase.refused_result(
            fake,
            "source and staging both present; refusing delete",
            staging_path=staging_path,
        )
    if not staging_present and not source_present:
        journal_ops.persist_target_state(
            host,
            operation_id,
            canonical_path=fake.canonical_path,
            state="external_disappeared",
            staging_path=str(staging_path),
        )
        return CleanupTargetResult(
            subject_type=fake.subject_type,
            subject_id=fake.subject_id,
            run_id=fake.run_id,
            root_relative_path=fake.root_relative_path,
            canonical_path=fake.canonical_path,
            status=TargetStatus.EXTERNAL_DISAPPEARED,
            message="source and staging both absent",
            staging_path=str(staging_path),
            filesystem_dev=fake.filesystem_dev,
            filesystem_ino=fake.filesystem_ino,
        )
    # source present, staging absent — not yet mutated; leave planned
    return CleanupTargetResult(
        subject_type=fake.subject_type,
        subject_id=fake.subject_id,
        run_id=fake.run_id,
        root_relative_path=fake.root_relative_path,
        canonical_path=fake.canonical_path,
        status=TargetStatus.SKIPPED,
        message="source still present; staging absent (not yet mutated)",
        staging_path=str(staging_path),
        filesystem_dev=fake.filesystem_dev,
        filesystem_ino=fake.filesystem_ino,
    )


def retry_interrupted_staging(host, operation_id: str) -> CleanupResult:
    logger.info("cleanup retry start operation_id=%s", operation_id)
    try:
        journal.validate_operation_id(operation_id)
    except ValueError:
        return CleanupResult(
            operation_id=operation_id,
            plan_id="",
            mode=CleanupMode.DELETE_ALL,
            status=CleanupStatus.BLOCKED,
            targets=(),
            warnings=(),
            errors=(f"Invalid operation_id: {operation_id}",),
        )
    # Gate before load/claim
    gate = try_run_tree_mutation_gate(state_dir=host.state_dir)
    if gate is None:
        return CleanupResult(
            operation_id=operation_id,
            plan_id="",
            mode=CleanupMode.DELETE_ALL,
            status=CleanupStatus.BLOCKED,
            targets=(),
            warnings=(),
            errors=(CLEANUP_BUSY, "Could not acquire run-tree mutation gate"),
        )
    locks: list[RunWriterLock] = []
    try:
        loaded = journal.load_operation_typed(
            host.state_dir,
            operation_id,
            expected_policy_version=CLEANUP_POLICY_VERSION,
            expected_schema_version=JOURNAL_SCHEMA_VERSION,
        )
        if loaded.kind is journal.JournalLoadKind.MISSING:
            return CleanupResult(
                operation_id=operation_id,
                plan_id="",
                mode=CleanupMode.DELETE_ALL,
                status=CleanupStatus.BLOCKED,
                targets=(),
                warnings=(),
                errors=("Unknown operation journal",),
            )
        if loaded.kind is journal.JournalLoadKind.INCOMPATIBLE:
            return CleanupResult(
                operation_id=operation_id,
                plan_id="",
                mode=CleanupMode.DELETE_ALL,
                status=CleanupStatus.BLOCKED,
                targets=(),
                warnings=(),
                errors=(loaded.message or "Incompatible journal schema/policy",),
            )
        if loaded.kind is journal.JournalLoadKind.CORRUPT_OR_UNSAFE:
            return CleanupResult(
                operation_id=operation_id,
                plan_id="",
                mode=CleanupMode.DELETE_ALL,
                status=CleanupStatus.BLOCKED,
                targets=(),
                warnings=(),
                errors=(loaded.message or "Corrupt or unsafe journal",),
            )
        data = loaded.data or {}
        mode = CleanupMode(data.get("mode") or CleanupMode.DELETE_ALL.value)
        plan_id = str(data.get("plan_id") or "")
        if loaded.kind is journal.JournalLoadKind.TERMINAL:
            return _synthesize_terminal_result(
                operation_id=operation_id,
                plan_id=plan_id,
                mode=mode,
                data=data,
            )
        try:
            claim_dur = journal.claim_retry_ownership(host.state_dir, operation_id)
            if claim_dur.outcome is journal.DirFsyncOutcome.FAILED:
                return CleanupResult(
                    operation_id=operation_id,
                    plan_id=plan_id,
                    mode=mode,
                    status=CleanupStatus.BLOCKED,
                    targets=(),
                    warnings=(),
                    errors=(
                        f"retry claim journal durability failed: {claim_dur.message}",
                    ),
                )
        except Exception as exc:  # noqa: BLE001
            return CleanupResult(
                operation_id=operation_id,
                plan_id=plan_id,
                mode=mode,
                status=CleanupStatus.BLOCKED,
                targets=(),
                warnings=(),
                errors=(f"could not claim retry ownership: {exc}",),
            )
        roots, blocking = validate_roots(host)
        if blocking:
            return CleanupResult(
                operation_id=operation_id,
                plan_id=plan_id,
                mode=mode,
                status=CleanupStatus.BLOCKED,
                targets=(),
                warnings=(),
                errors=tuple(blocking),
            )
        results: list[CleanupTargetResult] = []
        deleted = 0
        visible = 0
        errors: list[str] = []
        warnings: list[str] = []
        journal_durability_failed = False
        targets = sorted(
            data.get("targets", []),
            key=lambda t: str(t.get("canonical_path") or ""),
        )
        for target in targets:
            state = str(target.get("state") or "")
            if state not in journal.PENDING_TARGET_STATES:
                continue
            fake = CleanupTarget(
                subject_type=SubjectType(target["subject_type"]),
                subject_id=str(target["subject_id"]),
                run_id=str(target["run_id"]),
                root_relative_path=str(target.get("root_relative_path") or ""),
                canonical_path=str(target["canonical_path"]),
                mtime_ns=0,
                filesystem_dev=int(target.get("filesystem_dev") or 0),
                filesystem_ino=int(target.get("filesystem_ino") or 0),
                size_estimate_bytes=0,
                file_count=0,
                tree_fingerprint=str(target.get("tree_fingerprint") or ("0" * 64)),
                safety_status=EntryClassification.eligible,
            )
            schema_ver = int(
                data.get("journal_schema_version") or JOURNAL_SCHEMA_VERSION
            )
            # Prefer durable journal staging_path; else schema-dispatched derive.
            staging_path = journal.derive_staging_path_from_journal_target(
                output_root_for_target(host, fake),
                operation_id,
                target,
                journal_schema_version=schema_ver,
            )
            # Acquire run lock BEFORE any staged-tree verification
            run_lock = try_per_run_lock(fake.canonical_path, state_dir=host.state_dir)
            if run_lock is None:
                results.append(
                    CleanupTargetResult(
                        subject_type=fake.subject_type,
                        subject_id=fake.subject_id,
                        run_id=fake.run_id,
                        root_relative_path=fake.root_relative_path,
                        canonical_path=fake.canonical_path,
                        status=TargetStatus.LOCKED_SKIP,
                        message="per-run lock unavailable during retry",
                        staging_path=str(staging_path),
                        filesystem_dev=fake.filesystem_dev,
                        filesystem_ino=fake.filesystem_ino,
                    )
                )
                continue
            locks.append(run_lock)

            # Verified/partial + staging absent + source absent → already deleted.
            # Never reconcile when the source path still exists.
            staging_absent = not fd_ops.lexists(staging_path)
            source_absent = not fd_ops.lexists(fake.canonical_path)
            if (
                state in {"physical_delete_verified", "physical_delete_partial"}
                and staging_absent
                and source_absent
            ):
                journal_ops.persist_target_state(
                    host,
                    operation_id,
                    canonical_path=fake.canonical_path,
                    state="physical_deleted",
                    staging_path=str(staging_path),
                )
                results.append(
                    CleanupTargetResult(
                        subject_type=fake.subject_type,
                        subject_id=fake.subject_id,
                        run_id=fake.run_id,
                        root_relative_path=fake.root_relative_path,
                        canonical_path=fake.canonical_path,
                        status=TargetStatus.PHYSICAL_DELETED,
                        message=(
                            f"reconciled {state} " "(staging absent, source absent)"
                        ),
                        staging_path=str(staging_path),
                        filesystem_dev=fake.filesystem_dev,
                        filesystem_ino=fake.filesystem_ino,
                    )
                )
                deleted += 1
                visible += 1
                continue

            if state in {"planned", "staging_started"}:
                reconciled = reconcile_planned_or_started_target(
                    host,
                    operation_id=operation_id,
                    target_row=target,
                    fake=fake,
                    staging_path=staging_path,
                )
                if reconciled is not None:
                    results.append(reconciled)
                    if reconciled.status is TargetStatus.EXTERNAL_DISAPPEARED:
                        deleted += 1
                        visible += 1
                    elif reconciled.status in {
                        TargetStatus.PHYSICAL_DELETE_REFUSED,
                    }:
                        errors.append(reconciled.message)
                        visible += 1
                    continue
                # Fall through to physical delete after recovery
                state = "recovered_from_incomplete_stage"
                visible += 1
            else:
                visible += 1

            # physical_delete_verified may have already removed descendants,
            # so the planned fingerprint is no longer valid — resume without it.
            require_fp = state not in {
                "physical_delete_partial",
                "physical_delete_verified",
            } and not target.get("fingerprint_invalidated")
            staged_dev = (
                int(target["staged_dev"])
                if target.get("staged_dev") is not None
                else None
            )
            staged_ino = (
                int(target["staged_ino"])
                if target.get("staged_ino") is not None
                else None
            )
            # Crash-window recovery via lstat (never Path.exists)
            if staged_dev is None and fd_ops.lexists(staging_path):
                try:
                    st = fd_ops.lstat_nofollow(staging_path)
                    if (
                        int(st.st_dev) == fake.filesystem_dev
                        and int(st.st_ino) == fake.filesystem_ino
                    ):
                        staged_dev = int(st.st_dev)
                        staged_ino = int(st.st_ino)
                        journal_ops.persist_target_state(
                            host,
                            operation_id,
                            canonical_path=fake.canonical_path,
                            state="recovered_from_incomplete_stage",
                            staging_path=str(staging_path),
                            staged_dev=staged_dev,
                            staged_ino=staged_ino,
                        )
                except OSError:
                    pass
            tr = deletion_phase.physical_delete_one(
                host,
                fake,
                staging_path,
                operation_id,
                staged_dev=staged_dev,
                staged_ino=staged_ino,
                require_fingerprint=require_fp,
            )
            results.append(tr)
            if tr.status is TargetStatus.PHYSICAL_DELETED:
                deleted += 1
                if "journal durability failed" in (tr.message or ""):
                    journal_durability_failed = True
                    errors.append(tr.message)
            elif tr.status is TargetStatus.PHYSICAL_DELETE_REFUSED:
                errors.append(tr.message)
            elif tr.status is TargetStatus.PHYSICAL_DELETE_PARTIAL:
                errors.append(tr.message)
            elif tr.status is TargetStatus.PHYSICAL_DELETE_FAILED:
                errors.append(tr.message)
        # Invalidate caches when any visible removal was known
        if visible:
            for w in finalization.invalidate_caches(host):
                warnings.append(w)
        # Authoritative status from complete journal target vector
        try:
            status = results_mod.status_from_loaded_operation(
                host.state_dir, operation_id
            )
        except Exception as exc:  # noqa: BLE001
            status = CleanupStatus.PARTIAL
            errors.append(f"could not derive status from journal: {exc}")
        if journal_durability_failed and status is CleanupStatus.SUCCESS:
            status = CleanupStatus.PARTIAL
        if any(r.status is TargetStatus.LOCKED_SKIP for r in results):
            if status is CleanupStatus.SUCCESS:
                status = CleanupStatus.PARTIAL
        try:
            dur = journal.update_operation_status(
                host.state_dir, operation_id, status.value
            )
            if dur.outcome is journal.DirFsyncOutcome.FAILED:
                errors.append(
                    f"retry terminal journal durability failed: {dur.message}"
                )
                if status is CleanupStatus.SUCCESS:
                    status = CleanupStatus.PARTIAL
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
            if status is CleanupStatus.SUCCESS:
                status = CleanupStatus.PARTIAL
        result = CleanupResult(
            operation_id=operation_id,
            plan_id=plan_id,
            mode=mode,
            status=status,
            targets=tuple(results),
            warnings=tuple(warnings),
            errors=tuple(errors),
            visible_removed_count=visible,
            physically_deleted_count=deleted,
        )
        logger.info(
            "cleanup retry finished status=%s operation_id=%s "
            "visible_removed=%d physically_deleted=%d",
            result.status.value,
            result.operation_id,
            result.visible_removed_count,
            result.physically_deleted_count,
        )
        return result
    finally:
        locking.release_locks(locks)
        gate.release()
