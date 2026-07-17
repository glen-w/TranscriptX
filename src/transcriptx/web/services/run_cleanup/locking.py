"""Per-run locks, identity walks, and locked rediscovery (Phase A extract)."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from transcriptx.core.utils.run_writer_locks import RunWriterLock, try_per_run_lock
from transcriptx.web.services.run_cleanup import fd_ops
from transcriptx.web.services.run_cleanup.execution_compare import (
    compare_with_lock_skip_masks,
)
from transcriptx.web.services.run_cleanup.faults import fault_point
from transcriptx.web.services.run_cleanup.fingerprint import (
    TreeFingerprintError,
    compute_tree_fingerprint,
)
from transcriptx.web.services.run_cleanup.models import (
    CleanupMode,
    CleanupPlan,
    CleanupStatus,
    CleanupTarget,
    CleanupTargetResult,
    RootIdentity,
    SubjectType,
    TargetStatus,
)
from transcriptx.web.services.run_cleanup.staging import (
    StagingPlatformUnsupportedError,
    StagingUnsafeError,
)


def acquire_locks(
    host, plan: CleanupPlan
) -> tuple[list[RunWriterLock], list[CleanupTargetResult], str | None]:
    results: list[CleanupTargetResult] = []
    locks: list[RunWriterLock] = []
    if plan.mode is CleanupMode.DELETE_ALL:
        ordered = sorted(plan.candidates, key=lambda t: t.canonical_path)
        for target in ordered:
            fault_point("before_per_run_lock")
            lock = try_per_run_lock(target.canonical_path, state_dir=host.state_dir)
            if lock is None:
                results.append(
                    CleanupTargetResult(
                        subject_type=target.subject_type,
                        subject_id=target.subject_id,
                        run_id=target.run_id,
                        root_relative_path=target.root_relative_path,
                        canonical_path=target.canonical_path,
                        status=TargetStatus.LOCKED_SKIP,
                        message="per-run lock unavailable",
                        filesystem_dev=target.filesystem_dev,
                        filesystem_ino=target.filesystem_ino,
                        root_kind=target.subject_type,
                    )
                )
                continue
            locks.append(lock)
        return locks, results, None

    all_targets = list(plan.candidates) + list(plan.retained)
    by_canon: dict[str, CleanupTarget] = {t.canonical_path: t for t in all_targets}
    ordered = sorted(by_canon.values(), key=lambda t: t.canonical_path)
    subject_locks: dict[tuple[SubjectType, str], list[RunWriterLock]] = defaultdict(
        list
    )
    subject_failed: set[tuple[SubjectType, str]] = set()
    candidate_ids = {(c.subject_type, c.subject_id, c.run_id) for c in plan.candidates}
    for target in ordered:
        subject_key = (target.subject_type, target.subject_id)
        if subject_key in subject_failed:
            continue
        fault_point("before_per_run_lock")
        lock = try_per_run_lock(target.canonical_path, state_dir=host.state_dir)
        if lock is None:
            for held in subject_locks[subject_key]:
                held.release()
            subject_locks[subject_key] = []
            subject_failed.add(subject_key)
            continue
        subject_locks[subject_key].append(lock)
    for subject_key in subject_failed:
        for target in all_targets:
            if (target.subject_type, target.subject_id) != subject_key:
                continue
            key = (target.subject_type, target.subject_id, target.run_id)
            if key not in candidate_ids:
                continue
            results.append(
                CleanupTargetResult(
                    subject_type=target.subject_type,
                    subject_id=target.subject_id,
                    run_id=target.run_id,
                    root_relative_path=target.root_relative_path,
                    canonical_path=target.canonical_path,
                    status=TargetStatus.SUBJECT_LOCKED_SKIP,
                    message="could not lock all runs in subject",
                    filesystem_dev=target.filesystem_dev,
                    filesystem_ino=target.filesystem_ino,
                    root_kind=target.subject_type,
                )
            )
    for subject_key, held in subject_locks.items():
        if subject_key in subject_failed:
            continue
        locks.extend(held)
    return locks, results, None


def release_locks(locks: list[RunWriterLock]) -> None:
    for lock in reversed(locks):
        try:
            lock.release()
        except Exception:
            pass


def fd_walk_run_identity(host, root: RootIdentity, target: CleanupTarget) -> None:
    """Descriptor-anchored root → subject → run identity proof via fd_ops."""
    if not fd_ops.platform_supports_secure_cleanup():
        raise StagingPlatformUnsupportedError(
            "missing descriptor primitives for path walk"
        )
    if root.dev is None or root.ino is None:
        raise StagingUnsafeError("root identity incomplete")
    root_path = Path(root.configured_path)
    root_fd = fd_ops.open_dir_nofollow(root_path)
    try:
        st = fd_ops.fstat_fd(root_fd)
        if int(st.st_dev) != int(root.dev) or int(st.st_ino) != int(root.ino):
            raise StagingUnsafeError("root fstat identity mismatch")
        parts = Path(target.root_relative_path).parts
        if len(parts) != 2:
            raise StagingUnsafeError("expected subject/run relative path")
        subject_name, run_name = parts
        sub_fd = fd_ops.open_dir_nofollow(subject_name, dir_fd=root_fd)
        try:
            run_fd = fd_ops.open_dir_nofollow(run_name, dir_fd=sub_fd)
            try:
                run_st = fd_ops.fstat_fd(run_fd)
                if int(run_st.st_dev) != int(target.filesystem_dev) or int(
                    run_st.st_ino
                ) != int(target.filesystem_ino):
                    raise StagingUnsafeError("run fstat identity mismatch")
            finally:
                fd_ops.close_quiet(run_fd)
        finally:
            fd_ops.close_quiet(sub_fd)
    finally:
        fd_ops.close_quiet(root_fd)


def revalidate_execution_set_under_lock(
    host,
    plan: CleanupPlan,
    lock_results: list[CleanupTargetResult],
) -> tuple[list[CleanupTargetResult], CleanupStatus | None]:
    from transcriptx.web.services.run_cleanup.plan_builder import (
        build_execution_set,
    )

    results: list[CleanupTargetResult] = list(lock_results)
    roots, blocking = host._validate_roots()
    if blocking:
        results.append(
            CleanupTargetResult(
                subject_type=SubjectType.transcript,
                subject_id="",
                run_id="",
                root_relative_path="",
                canonical_path="",
                status=TargetStatus.STALE,
                message="; ".join(blocking),
            )
        )
        return results, CleanupStatus.BLOCKED

    es = build_execution_set(
        plan.mode,
        roots,
        blocking,
        host.outputs_dir,
        host.group_outputs_dir,
    )
    ok, reason = compare_with_lock_skip_masks(
        planned=plan, rediscovered=es, lock_results=lock_results
    )
    if not ok:
        results.append(
            CleanupTargetResult(
                subject_type=SubjectType.transcript,
                subject_id="",
                run_id="",
                root_relative_path="",
                canonical_path="",
                status=TargetStatus.STALE,
                message=reason,
            )
        )
        return results, CleanupStatus.STALE_PLAN

    locked_skip_keys = {
        (r.subject_type, r.subject_id, r.run_id)
        for r in lock_results
        if r.status is TargetStatus.LOCKED_SKIP
    }
    subject_skip_keys = {
        (r.subject_type, r.subject_id)
        for r in lock_results
        if r.status is TargetStatus.SUBJECT_LOCKED_SKIP
    }

    def _is_masked(t: CleanupTarget) -> bool:
        if (t.subject_type, t.subject_id, t.run_id) in locked_skip_keys:
            return True
        if (t.subject_type, t.subject_id) in subject_skip_keys:
            return True
        return False

    for target in list(plan.candidates) + (
        list(plan.retained) if plan.mode is CleanupMode.DELETE_OLD else []
    ):
        root = host._planned_root_for_target(plan, target)
        try:
            host._fd_walk_run_identity(root, target)
        except StagingPlatformUnsupportedError as exc:
            results.append(
                CleanupTargetResult(
                    subject_type=target.subject_type,
                    subject_id=target.subject_id,
                    run_id=target.run_id,
                    root_relative_path=target.root_relative_path,
                    canonical_path=target.canonical_path,
                    status=TargetStatus.STALE,
                    message=str(exc),
                )
            )
            return results, CleanupStatus.BLOCKED
        except (StagingUnsafeError, OSError, fd_ops.FdOpsUnsupportedError) as exc:
            results.append(
                CleanupTargetResult(
                    subject_type=target.subject_type,
                    subject_id=target.subject_id,
                    run_id=target.run_id,
                    root_relative_path=target.root_relative_path,
                    canonical_path=target.canonical_path,
                    status=TargetStatus.STALE,
                    message=str(exc),
                )
            )
            return results, CleanupStatus.STALE_PLAN
        if _is_masked(target):
            continue
        path = Path(target.canonical_path)
        try:
            fp, _, _ = compute_tree_fingerprint(path, int(target.filesystem_dev))
        except (OSError, TreeFingerprintError) as exc:
            results.append(
                CleanupTargetResult(
                    subject_type=target.subject_type,
                    subject_id=target.subject_id,
                    run_id=target.run_id,
                    root_relative_path=target.root_relative_path,
                    canonical_path=target.canonical_path,
                    status=TargetStatus.STALE,
                    message=str(exc),
                )
            )
            return results, CleanupStatus.STALE_PLAN
        if fp != target.tree_fingerprint:
            results.append(
                CleanupTargetResult(
                    subject_type=target.subject_type,
                    subject_id=target.subject_id,
                    run_id=target.run_id,
                    root_relative_path=target.root_relative_path,
                    canonical_path=target.canonical_path,
                    status=TargetStatus.STALE,
                    message="tree fingerprint mismatch",
                )
            )
            return results, CleanupStatus.STALE_PLAN
    return results, None
