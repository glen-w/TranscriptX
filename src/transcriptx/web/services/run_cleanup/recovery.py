"""Pending-journal reconciliation and retry sequencing — Phase A extract."""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.run_writer_locks import (
    RunWriterLock,
    try_per_run_lock,
    try_run_tree_mutation_gate,
)
from transcriptx.web.services.run_cleanup import fd_ops
from transcriptx.web.services.run_cleanup import journal
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
                host._persist_target_state(
                    operation_id,
                    canonical_path=fake.canonical_path,
                    state="recovered_from_incomplete_stage",
                    staging_path=str(staging_path),
                    staged_dev=int(st.st_dev),
                    staged_ino=int(st.st_ino),
                )
                return None  # proceed to physical delete
        except OSError as exc:
            return CleanupTargetResult(
                subject_type=fake.subject_type,
                subject_id=fake.subject_id,
                run_id=fake.run_id,
                root_relative_path=fake.root_relative_path,
                canonical_path=fake.canonical_path,
                status=TargetStatus.PHYSICAL_DELETE_REFUSED,
                message=f"cannot reconcile staged remnant: {exc}",
                staging_path=str(staging_path),
                filesystem_dev=fake.filesystem_dev,
                filesystem_ino=fake.filesystem_ino,
            )
        return CleanupTargetResult(
            subject_type=fake.subject_type,
            subject_id=fake.subject_id,
            run_id=fake.run_id,
            root_relative_path=fake.root_relative_path,
            canonical_path=fake.canonical_path,
            status=TargetStatus.PHYSICAL_DELETE_REFUSED,
            message="staging present but identity does not match journal",
            staging_path=str(staging_path),
            filesystem_dev=fake.filesystem_dev,
            filesystem_ino=fake.filesystem_ino,
        )
    if staging_present and source_present:
        return CleanupTargetResult(
            subject_type=fake.subject_type,
            subject_id=fake.subject_id,
            run_id=fake.run_id,
            root_relative_path=fake.root_relative_path,
            canonical_path=fake.canonical_path,
            status=TargetStatus.PHYSICAL_DELETE_REFUSED,
            message="source and staging both present; refusing delete",
            staging_path=str(staging_path),
            filesystem_dev=fake.filesystem_dev,
            filesystem_ino=fake.filesystem_ino,
        )
    if not staging_present and not source_present:
        host._persist_target_state(
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
            return CleanupResult(
                operation_id=operation_id,
                plan_id=plan_id,
                mode=mode,
                status=CleanupStatus.NOOP,
                targets=(),
                warnings=("Operation already terminal",),
                errors=(),
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
        roots, blocking = host._validate_roots()
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
            staging_path = journal.intended_staging_path(
                host._output_root_for_target(fake), operation_id, fake
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
                host._persist_target_state(
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
                reconciled = host._reconcile_planned_or_started_target(
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
                        host._persist_target_state(
                            operation_id,
                            canonical_path=fake.canonical_path,
                            state="recovered_from_incomplete_stage",
                            staging_path=str(staging_path),
                            staged_dev=staged_dev,
                            staged_ino=staged_ino,
                        )
                except OSError:
                    pass
            tr = host._physical_delete_one(
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
            for w in host._invalidate_caches():
                warnings.append(w)
        # Authoritative status from complete journal target vector
        try:
            status = host._status_from_loaded_operation(operation_id)
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
        host._release_locks(locks)
        gate.release()
