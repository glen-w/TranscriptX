"""Staging orchestration (_stage_one) — Phase A extract."""

from __future__ import annotations

from transcriptx.web.services.run_cleanup import journal
from pathlib import Path

from transcriptx.web.services.run_cleanup import fd_ops
from transcriptx.web.services.run_cleanup.faults import fault_point
from transcriptx.web.services.run_cleanup.models import (
    CleanupPlan,
    CleanupTarget,
    CleanupTargetResult,
    StageOutcome,
    TargetStatus,
)
from transcriptx.web.services.run_cleanup.staging import (
    StagingPlatformUnsupportedError,
    StagingUnsafeError,
    ensure_secure_staging_directory,
    rename_into_staging,
)


def stage_one(
    host,
    target: CleanupTarget,
    operation_id: str,
    plan: CleanupPlan,
    *,
    allow_existing_operation_dir: bool = False,
) -> StageOutcome:
    rename_attempted = False
    visible_removed = False
    staged_dev: int | None = None
    staged_ino: int | None = None
    staging_path: str | None = None
    layout = None
    basename: str | None = None

    def _identity_unverified_outcome(
        message: str,
        *,
        errors: tuple[str, ...] = (),
        warnings: tuple[str, ...] = (),
    ) -> StageOutcome:
        host._persist_target_state(
            operation_id,
            canonical_path=target.canonical_path,
            state="staged_identity_unverified",
            staging_path=staging_path,
            staged_dev=staged_dev,
            staged_ino=staged_ino,
            extra={"error": message},
        )
        return StageOutcome(
            target=target,
            staging_path=staging_path,
            rename_attempted=True,
            visible_removed=True,
            staged_dev=staged_dev,
            staged_ino=staged_ino,
            journal_updated=False,
            deletion_ready=False,
            target_result=CleanupTargetResult(
                subject_type=target.subject_type,
                subject_id=target.subject_id,
                run_id=target.run_id,
                root_relative_path=target.root_relative_path,
                canonical_path=target.canonical_path,
                status=TargetStatus.STAGED_IDENTITY_UNVERIFIED,
                message=message,
                staging_path=staging_path,
                filesystem_dev=target.filesystem_dev,
                filesystem_ino=target.filesystem_ino,
                root_kind=target.subject_type,
            ),
            errors=errors or (message,),
            warnings=warnings,
        )

    try:
        root = host._planned_root_for_target(plan, target)
        layout = ensure_secure_staging_directory(
            host._output_root_for_target(target),
            operation_id,
            target,
            root,
            allow_existing_operation_dir=allow_existing_operation_dir,
        )
        staging_path = str(layout.staging_dest)
        basename = layout.basename
        # Durable intent before rename — crash after this is recoverable.
        host._persist_target_state(
            operation_id,
            canonical_path=target.canonical_path,
            state="staging_started",
            staging_path=staging_path,
            require_durable=True,
        )
        rename_into_staging(
            Path(target.canonical_path),
            layout,
            expected_dev=target.filesystem_dev,
            expected_ino=target.filesystem_ino,
            root_relative_path=target.root_relative_path,
        )
        rename_attempted = True
        visible_removed = True  # IMMEDIATELY after successful rename
    except StagingPlatformUnsupportedError:
        if layout is not None:
            layout.close()
        raise
    except journal.JournalDurabilityError as exc:
        if layout is not None:
            layout.close()
            layout = None
        tr = CleanupTargetResult(
            subject_type=target.subject_type,
            subject_id=target.subject_id,
            run_id=target.run_id,
            root_relative_path=target.root_relative_path,
            canonical_path=target.canonical_path,
            status=TargetStatus.STAGING_FAILED,
            message=f"staging_started journal durability failed: {exc}",
            staging_path=staging_path,
            filesystem_dev=target.filesystem_dev,
            filesystem_ino=target.filesystem_ino,
            root_kind=target.subject_type,
        )
        return StageOutcome(
            target=target,
            staging_path=staging_path,
            rename_attempted=False,
            visible_removed=False,
            staged_dev=None,
            staged_ino=None,
            journal_updated=False,
            deletion_ready=False,
            target_result=tr,
            errors=(str(exc),),
        )
    except Exception as exc:  # noqa: BLE001
        if layout is not None:
            layout.close()
            layout = None
        if visible_removed:
            return _identity_unverified_outcome(str(exc))
        host._persist_target_state(
            operation_id,
            canonical_path=target.canonical_path,
            state="staging_failed",
            staging_path=staging_path,
            extra={"error": str(exc)},
        )
        tr = CleanupTargetResult(
            subject_type=target.subject_type,
            subject_id=target.subject_id,
            run_id=target.run_id,
            root_relative_path=target.root_relative_path,
            canonical_path=target.canonical_path,
            status=TargetStatus.STAGING_FAILED,
            message=str(exc),
            staging_path=staging_path,
            filesystem_dev=target.filesystem_dev,
            filesystem_ino=target.filesystem_ino,
            root_kind=target.subject_type,
        )
        return StageOutcome(
            target=target,
            staging_path=staging_path,
            rename_attempted=rename_attempted,
            visible_removed=False,
            staged_dev=None,
            staged_ino=None,
            journal_updated=False,
            deletion_ready=False,
            target_result=tr,
            errors=(str(exc),),
        )

    # Post-rename identity via operation_fd (layout still open)
    try:
        fault_point("before_staged_lstat")
        if layout is None or layout.operation_fd is None or basename is None:
            raise StagingUnsafeError("staging layout unavailable for post-rename proof")
        post = fd_ops.lstat_nofollow(basename, dir_fd=layout.operation_fd)
        fault_point("after_staged_lstat")
        staged_dev = int(post.st_dev)
        staged_ino = int(post.st_ino)
        if staged_dev != int(target.filesystem_dev) or staged_ino != int(
            target.filesystem_ino
        ):
            return _identity_unverified_outcome(
                "post-rename identity mismatch; left staged"
            )
        if fd_ops.lexists(target.canonical_path):
            return _identity_unverified_outcome("source still present after rename")
    except Exception as exc:  # noqa: BLE001
        return _identity_unverified_outcome(
            f"post-rename lstat failed: {exc}",
            warnings=(str(exc),),
        )
    finally:
        if layout is not None:
            layout.close()
            layout = None

    try:
        fault_point("before_post_rename_journal")
        dur = journal.update_target_state(
            host.state_dir,
            operation_id,
            canonical_path=target.canonical_path,
            state="staged",
            staging_path=staging_path,
            staged_dev=staged_dev,
            staged_ino=staged_ino,
        )
        if dur.outcome is journal.DirFsyncOutcome.FAILED:
            raise journal.JournalDurabilityError(dur.message)
    except Exception as exc:  # noqa: BLE001
        host._persist_target_state(
            operation_id,
            canonical_path=target.canonical_path,
            state="staged_journal_incomplete",
            staging_path=staging_path,
            staged_dev=staged_dev,
            staged_ino=staged_ino,
            extra={"error": str(exc)},
        )
        return StageOutcome(
            target=target,
            staging_path=staging_path,
            rename_attempted=True,
            visible_removed=True,
            staged_dev=staged_dev,
            staged_ino=staged_ino,
            journal_updated=False,
            deletion_ready=False,
            target_result=CleanupTargetResult(
                subject_type=target.subject_type,
                subject_id=target.subject_id,
                run_id=target.run_id,
                root_relative_path=target.root_relative_path,
                canonical_path=target.canonical_path,
                status=TargetStatus.STAGED_JOURNAL_INCOMPLETE,
                message=f"journal update failed: {exc}",
                staging_path=staging_path,
                filesystem_dev=target.filesystem_dev,
                filesystem_ino=target.filesystem_ino,
                root_kind=target.subject_type,
            ),
            errors=(str(exc),),
            warnings=(str(exc),),
        )

    return StageOutcome(
        target=target,
        staging_path=staging_path,
        rename_attempted=True,
        visible_removed=True,
        staged_dev=staged_dev,
        staged_ino=staged_ino,
        journal_updated=True,
        deletion_ready=True,
        target_result=CleanupTargetResult(
            subject_type=target.subject_type,
            subject_id=target.subject_id,
            run_id=target.run_id,
            root_relative_path=target.root_relative_path,
            canonical_path=target.canonical_path,
            status=TargetStatus.VISIBLE_REMOVED,
            message="renamed into staging",
            staging_path=staging_path,
            filesystem_dev=target.filesystem_dev,
            filesystem_ino=target.filesystem_ino,
            root_kind=target.subject_type,
        ),
    )
