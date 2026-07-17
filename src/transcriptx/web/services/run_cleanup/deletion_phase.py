"""Physical deletion orchestration and subject-parent prune — Phase A extract."""

from __future__ import annotations

import errno
import os
import stat
from pathlib import Path

from transcriptx.web.services.run_cleanup import journal
from transcriptx.web.services.run_cleanup.models import (
    CleanupTarget,
    CleanupTargetResult,
    TargetStatus,
)
from transcriptx.web.services.run_cleanup.physical_delete import (
    PhysicalDeletePartialError,
    PhysicalDeleteUnsafeError,
    safe_rmtree_verified,
    verify_staged_tree,
)


def physical_delete_one(
    host,
    target: CleanupTarget,
    staging_dest: Path,
    operation_id: str,
    *,
    staged_dev: int | None = None,
    staged_ino: int | None = None,
    require_fingerprint: bool = True,
) -> CleanupTargetResult:
    if not journal.is_journal_recognised_staging_path(
        host.state_dir,
        staging_dest,
        operation_id=operation_id,
        subject_type=target.subject_type.value,
        subject_id=target.subject_id,
        run_id=target.run_id,
        canonical_path=target.canonical_path,
        outputs_dir=host.outputs_dir,
        group_outputs_dir=host.group_outputs_dir,
    ):
        host._persist_target_state(
            operation_id,
            canonical_path=target.canonical_path,
            state="physical_delete_refused",
            staging_path=str(staging_dest),
            extra={"error": "staging path not recognised by journal"},
        )
        return CleanupTargetResult(
            subject_type=target.subject_type,
            subject_id=target.subject_id,
            run_id=target.run_id,
            root_relative_path=target.root_relative_path,
            canonical_path=target.canonical_path,
            status=TargetStatus.PHYSICAL_DELETE_REFUSED,
            message="staging path not recognised by journal",
            staging_path=str(staging_dest),
            filesystem_dev=target.filesystem_dev,
            filesystem_ino=target.filesystem_ino,
            root_kind=target.subject_type,
        )
    try:
        proof = verify_staged_tree(
            staging_path=staging_dest,
            planned_filesystem_dev=target.filesystem_dev,
            planned_filesystem_ino=target.filesystem_ino,
            planned_fingerprint=(
                target.tree_fingerprint if require_fingerprint else None
            ),
            staged_dev=staged_dev,
            staged_ino=staged_ino,
            operation_id=operation_id,
            canonical_source_path=target.canonical_path,
            subject_type=target.subject_type.value,
            subject_id=target.subject_id,
            run_id=target.run_id,
            require_fingerprint=require_fingerprint,
        )
        # Bracket deletion: verified → deleted.
        host._persist_target_state(
            operation_id,
            canonical_path=target.canonical_path,
            state="physical_delete_verified",
            staging_path=str(staging_dest),
            staged_dev=proof.staged_dev,
            staged_ino=proof.staged_ino,
            require_durable=True,
        )
        safe_rmtree_verified(proof)
        try:
            dur = journal.update_target_state(
                host.state_dir,
                operation_id,
                canonical_path=target.canonical_path,
                state="physical_deleted",
            )
            if dur.outcome is journal.DirFsyncOutcome.FAILED:
                return CleanupTargetResult(
                    subject_type=target.subject_type,
                    subject_id=target.subject_id,
                    run_id=target.run_id,
                    root_relative_path=target.root_relative_path,
                    canonical_path=target.canonical_path,
                    status=TargetStatus.PHYSICAL_DELETED,
                    message=(
                        "physically deleted; journal durability failed: "
                        f"{dur.message}"
                    ),
                    staging_path=str(staging_dest),
                    filesystem_dev=target.filesystem_dev,
                    filesystem_ino=target.filesystem_ino,
                    root_kind=target.subject_type,
                )
        except Exception as exc:  # noqa: BLE001
            return CleanupTargetResult(
                subject_type=target.subject_type,
                subject_id=target.subject_id,
                run_id=target.run_id,
                root_relative_path=target.root_relative_path,
                canonical_path=target.canonical_path,
                status=TargetStatus.PHYSICAL_DELETED,
                message=f"physically deleted; journal durability failed: {exc}",
                staging_path=str(staging_dest),
                filesystem_dev=target.filesystem_dev,
                filesystem_ino=target.filesystem_ino,
                root_kind=target.subject_type,
            )
        return CleanupTargetResult(
            subject_type=target.subject_type,
            subject_id=target.subject_id,
            run_id=target.run_id,
            root_relative_path=target.root_relative_path,
            canonical_path=target.canonical_path,
            status=TargetStatus.PHYSICAL_DELETED,
            message="physically deleted",
            staging_path=str(staging_dest),
            filesystem_dev=target.filesystem_dev,
            filesystem_ino=target.filesystem_ino,
            root_kind=target.subject_type,
        )
    except journal.JournalDurabilityError as exc:
        host._persist_target_state(
            operation_id,
            canonical_path=target.canonical_path,
            state="physical_delete_failed",
            staging_path=str(staging_dest),
            staged_dev=staged_dev,
            staged_ino=staged_ino,
            extra={"error": str(exc)},
        )
        return CleanupTargetResult(
            subject_type=target.subject_type,
            subject_id=target.subject_id,
            run_id=target.run_id,
            root_relative_path=target.root_relative_path,
            canonical_path=target.canonical_path,
            status=TargetStatus.PHYSICAL_DELETE_FAILED,
            message=f"physical_delete_verified journal failed: {exc}",
            staging_path=str(staging_dest),
            filesystem_dev=target.filesystem_dev,
            filesystem_ino=target.filesystem_ino,
            root_kind=target.subject_type,
        )
    except PhysicalDeletePartialError as exc:
        host._persist_target_state(
            operation_id,
            canonical_path=target.canonical_path,
            state="physical_delete_partial",
            staging_path=str(staging_dest),
            staged_dev=staged_dev,
            staged_ino=staged_ino,
            extra={"fingerprint_invalidated": True, "error": str(exc)},
        )
        return CleanupTargetResult(
            subject_type=target.subject_type,
            subject_id=target.subject_id,
            run_id=target.run_id,
            root_relative_path=target.root_relative_path,
            canonical_path=target.canonical_path,
            status=TargetStatus.PHYSICAL_DELETE_PARTIAL,
            message=str(exc),
            staging_path=str(staging_dest),
            filesystem_dev=target.filesystem_dev,
            filesystem_ino=target.filesystem_ino,
            root_kind=target.subject_type,
        )
    except PhysicalDeleteUnsafeError as exc:
        host._persist_target_state(
            operation_id,
            canonical_path=target.canonical_path,
            state="physical_delete_refused",
            staging_path=str(staging_dest),
            staged_dev=staged_dev,
            staged_ino=staged_ino,
            extra={"error": str(exc)},
        )
        return CleanupTargetResult(
            subject_type=target.subject_type,
            subject_id=target.subject_id,
            run_id=target.run_id,
            root_relative_path=target.root_relative_path,
            canonical_path=target.canonical_path,
            status=TargetStatus.PHYSICAL_DELETE_REFUSED,
            message=str(exc),
            staging_path=str(staging_dest),
            filesystem_dev=target.filesystem_dev,
            filesystem_ino=target.filesystem_ino,
            root_kind=target.subject_type,
        )
    except OSError as exc:
        host._persist_target_state(
            operation_id,
            canonical_path=target.canonical_path,
            state="physical_delete_failed",
            staging_path=str(staging_dest),
            staged_dev=staged_dev,
            staged_ino=staged_ino,
            extra={"error": str(exc)},
        )
        return CleanupTargetResult(
            subject_type=target.subject_type,
            subject_id=target.subject_id,
            run_id=target.run_id,
            root_relative_path=target.root_relative_path,
            canonical_path=target.canonical_path,
            status=TargetStatus.PHYSICAL_DELETE_FAILED,
            message=str(exc),
            staging_path=str(staging_dest),
            filesystem_dev=target.filesystem_dev,
            filesystem_ino=target.filesystem_ino,
            root_kind=target.subject_type,
        )


def prune_subject_parent(host, target: CleanupTarget) -> str | None:
    subject_parent = Path(target.canonical_path).parent
    try:
        st = subject_parent.lstat()
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
            return f"subject parent unsafe to prune: {subject_parent}"
        for root in (host.outputs_dir, host.group_outputs_dir):
            try:
                if subject_parent.resolve() == Path(root).resolve():
                    return None
            except OSError:
                continue
        os.rmdir(str(subject_parent))
        return None
    except OSError as exc:
        if exc.errno in {errno.ENOTEMPTY, errno.EEXIST}:
            return None
        # macOS ENOTEMPTY
        if getattr(exc, "errno", None) == 66:
            return None
        return f"could not prune subject parent {subject_parent}: {exc}"
