"""Gate, handle claim, authorization, and top-level execute sequencing — Phase A extract."""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.run_writer_locks import (
    RunWriterLock,
    try_run_tree_mutation_gate,
)
from transcriptx.web.services.run_cleanup import fd_ops
from transcriptx.web.services.run_cleanup import handles as handle_store
from transcriptx.web.services.run_cleanup.context import ExecutionAccumulator
from transcriptx.web.services.run_cleanup.faults import fault_point
from transcriptx.web.services.run_cleanup.models import (
    CLEANUP_BUSY,
    PLATFORM_UNSUPPORTED,
    CleanupAuthorization,
    CleanupPlan,
    CleanupResult,
    CleanupStatus,
    CleanupTargetResult,
    TargetStatus,
    authorization_is_valid,
)
from transcriptx.web.services.run_cleanup.staging import (
    StagingPlatformUnsupportedError,
    StagingUnsafeError,
    ensure_secure_staging_directory,
)

logger = get_logger()


def execute_cleanup(
    host,
    handle_token: str,
    authorization: CleanupAuthorization,
    session_id: str,
) -> CleanupResult:
    logger.info(
        "cleanup execute start mode=%s plan_id=%s",
        authorization.mode.value,
        authorization.plan_id,
    )
    gate = try_run_tree_mutation_gate(state_dir=host.state_dir)
    if gate is None:
        logger.warning("cleanup execute blocked: mutation gate busy")
        return host._result_on_gate_contention(handle_token, authorization, session_id)
    locks: list[RunWriterLock] = []
    try:
        result = host._execute_under_gate(
            handle_token, authorization, session_id, locks
        )
        logger.info(
            "cleanup execute finished status=%s operation_id=%s "
            "visible_removed=%d physically_deleted=%d errors=%d",
            result.status.value,
            result.operation_id or "(none)",
            result.visible_removed_count,
            result.physically_deleted_count,
            len(result.errors),
        )
        if result.errors:
            logger.warning(
                "cleanup execute errors: %s",
                "; ".join(result.errors[:5]),
            )
        return result
    finally:
        host._release_locks(locks)
        gate.release()


def result_on_gate_contention(
    host,
    handle_token: str,
    authorization: CleanupAuthorization,
    session_id: str,
) -> CleanupResult:
    state, _plan, prior = handle_store.peek_handle(handle_token, session_id)
    if state == "completed" and prior is not None:
        return CleanupResult(
            operation_id=prior.operation_id,
            plan_id=prior.plan_id,
            mode=prior.mode,
            status=CleanupStatus.ALREADY_EXECUTED,
            targets=prior.targets,
            warnings=prior.warnings + ("Handle already executed",),
            errors=prior.errors,
            visible_removed_count=prior.visible_removed_count,
            physically_deleted_count=prior.physically_deleted_count,
        )
    if state in {"in_progress", "completed"}:
        return CleanupResult(
            operation_id=prior.operation_id if prior else "",
            plan_id=prior.plan_id if prior else authorization.plan_id,
            mode=prior.mode if prior else authorization.mode,
            status=CleanupStatus.ALREADY_EXECUTED,
            targets=prior.targets if prior else (),
            warnings=("Handle already claimed or in progress",),
            errors=(),
            visible_removed_count=prior.visible_removed_count if prior else 0,
            physically_deleted_count=(prior.physically_deleted_count if prior else 0),
        )
    return CleanupResult(
        operation_id="",
        plan_id=authorization.plan_id,
        mode=authorization.mode,
        status=CleanupStatus.BLOCKED,
        targets=(),
        warnings=(),
        errors=(CLEANUP_BUSY, "Could not acquire run-tree mutation gate"),
    )


def execute_under_gate(
    host,
    handle_token: str,
    authorization: CleanupAuthorization,
    session_id: str,
    locks: list[RunWriterLock],
) -> CleanupResult:
    plan, prior = handle_store.claim_handle(handle_token, session_id)
    if plan is None and prior is not None:
        return CleanupResult(
            operation_id=prior.operation_id,
            plan_id=prior.plan_id,
            mode=prior.mode,
            status=CleanupStatus.ALREADY_EXECUTED,
            targets=prior.targets,
            warnings=prior.warnings + ("Handle already executed",),
            errors=prior.errors,
            visible_removed_count=prior.visible_removed_count,
            physically_deleted_count=prior.physically_deleted_count,
        )
    if plan is None:
        state, _, _ = handle_store.peek_handle(handle_token, session_id)
        if state in {"in_progress", "completed"}:
            return CleanupResult(
                operation_id="",
                plan_id=authorization.plan_id,
                mode=authorization.mode,
                status=CleanupStatus.ALREADY_EXECUTED,
                targets=(),
                warnings=("Handle already claimed or in progress",),
                errors=(),
            )
        return CleanupResult(
            operation_id="",
            plan_id=authorization.plan_id,
            mode=authorization.mode,
            status=CleanupStatus.BLOCKED,
            targets=(),
            warnings=(),
            errors=("Missing or expired cleanup handle",),
        )

    # Everything after a successful claim must store a result (never leave
    # the handle in_progress with no outcome).
    try:
        return host._execute_claimed(
            handle_token, authorization, session_id, locks, plan
        )
    except Exception as exc:  # noqa: BLE001
        result = CleanupResult(
            operation_id="",
            plan_id=plan.plan_id,
            mode=plan.mode,
            status=CleanupStatus.FAILED_BEFORE_MUTATION,
            targets=(),
            warnings=(),
            errors=(f"cleanup aborted before mutation: {exc}",),
        )
        try:
            handle_store.store_result(handle_token, session_id, result)
        except Exception:
            pass
        return result


def execute_claimed(
    host,
    handle_token: str,
    authorization: CleanupAuthorization,
    session_id: str,
    locks: list[RunWriterLock],
    plan: CleanupPlan,
) -> CleanupResult:
    if not authorization_is_valid(
        authorization,
        expected_mode=plan.mode,
        expected_plan_id=plan.plan_id,
    ):
        logger.warning("cleanup blocked: authorization failed plan_id=%s", plan.plan_id)
        result = CleanupResult(
            operation_id="",
            plan_id=plan.plan_id,
            mode=plan.mode,
            status=CleanupStatus.BLOCKED,
            targets=(),
            warnings=(),
            errors=(
                "Authorization failed (acknowledgement / phrase / plan_id / mode)",
            ),
        )
        handle_store.store_result(handle_token, session_id, result)
        return result

    if not fd_ops.platform_supports_secure_cleanup():
        result = CleanupResult(
            operation_id="",
            plan_id=plan.plan_id,
            mode=plan.mode,
            status=CleanupStatus.BLOCKED,
            targets=(),
            warnings=(),
            errors=(
                PLATFORM_UNSUPPORTED,
                "Platform lacks required staging/deletion primitives",
            ),
        )
        handle_store.store_result(handle_token, session_id, result)
        return result

    if plan.blocking_errors:
        result = CleanupResult(
            operation_id="",
            plan_id=plan.plan_id,
            mode=plan.mode,
            status=CleanupStatus.BLOCKED,
            targets=(),
            warnings=plan.warnings,
            errors=plan.blocking_errors,
        )
        handle_store.store_result(handle_token, session_id, result)
        return result

    rediscovered = host._build_plan(plan.mode)
    if rediscovered.plan_id != plan.plan_id or rediscovered.blocking_errors:
        result = CleanupResult(
            operation_id="",
            plan_id=plan.plan_id,
            mode=plan.mode,
            status=CleanupStatus.STALE_PLAN,
            targets=(),
            warnings=rediscovered.warnings,
            errors=rediscovered.blocking_errors
            or ("Plan stale after rediscovery (plan_id mismatch)",),
        )
        handle_store.store_result(handle_token, session_id, result)
        return result
    plan = rediscovered

    if not plan.candidates:
        logger.info(
            "cleanup noop: no candidates plan_id=%s mode=%s",
            plan.plan_id,
            plan.mode.value,
        )
        result = CleanupResult(
            operation_id="",
            plan_id=plan.plan_id,
            mode=plan.mode,
            status=CleanupStatus.NOOP,
            targets=tuple(
                CleanupTargetResult(
                    subject_type=t.subject_type,
                    subject_id=t.subject_id,
                    run_id=t.run_id,
                    root_relative_path=t.root_relative_path,
                    canonical_path=t.canonical_path,
                    status=TargetStatus.RETAINED,
                )
                for t in plan.retained
            ),
            warnings=plan.warnings,
            errors=(),
        )
        handle_store.store_result(handle_token, session_id, result)
        return result

    acquired, lock_results, lock_error = host._acquire_locks(plan)
    locks.extend(acquired)
    fault_point("after_all_locks")
    if lock_error is not None:
        result = CleanupResult(
            operation_id="",
            plan_id=plan.plan_id,
            mode=plan.mode,
            status=CleanupStatus.FAILED_BEFORE_MUTATION,
            targets=tuple(lock_results),
            warnings=(),
            errors=(lock_error,),
        )
        handle_store.store_result(handle_token, session_id, result)
        return result

    stale_results, rediscovery_status = host._revalidate_execution_set_under_lock(
        plan, lock_results
    )
    fault_point("after_locked_rediscovery")
    if rediscovery_status is CleanupStatus.BLOCKED:
        result = CleanupResult(
            operation_id="",
            plan_id=plan.plan_id,
            mode=plan.mode,
            status=CleanupStatus.BLOCKED,
            targets=tuple(stale_results),
            warnings=(),
            errors=("Output roots unsafe or incomplete under lock",),
        )
        handle_store.store_result(handle_token, session_id, result)
        return result
    if rediscovery_status is CleanupStatus.STALE_PLAN or any(
        r.status is TargetStatus.STALE for r in stale_results
    ):
        result = CleanupResult(
            operation_id="",
            plan_id=plan.plan_id,
            mode=plan.mode,
            status=CleanupStatus.STALE_PLAN,
            targets=tuple(stale_results),
            warnings=(),
            errors=("Execution set mismatch under lock",),
        )
        handle_store.store_result(handle_token, session_id, result)
        return result

    skip_keys = {
        (r.subject_type, r.subject_id, r.run_id)
        for r in lock_results
        if r.status
        in {
            TargetStatus.LOCKED_SKIP,
            TargetStatus.SUBJECT_LOCKED_SKIP,
            TargetStatus.SKIPPED,
        }
    }
    to_mutate = [
        t
        for t in plan.candidates
        if (t.subject_type, t.subject_id, t.run_id) not in skip_keys
    ]
    if not to_mutate:
        result = CleanupResult(
            operation_id="",
            plan_id=plan.plan_id,
            mode=plan.mode,
            status=CleanupStatus.PARTIAL if lock_results else CleanupStatus.NOOP,
            targets=tuple(lock_results),
            warnings=(),
            errors=(),
        )
        handle_store.store_result(handle_token, session_id, result)
        return result

    operation_id = host._new_journaled_operation(plan, to_mutate)
    fault_point("after_initial_journal")
    logger.info(
        "cleanup journaled operation_id=%s plan_id=%s targets=%d",
        operation_id,
        plan.plan_id,
        len(to_mutate),
    )

    # Create exclusive operation staging dirs once per output root involved
    op_dirs_created: set[str] = set()
    try:
        for target in to_mutate:
            root_path = str(host._output_root_for_target(target))
            if root_path in op_dirs_created:
                continue
            root = host._planned_root_for_target(plan, target)
            layout = ensure_secure_staging_directory(
                host._output_root_for_target(target),
                operation_id,
                target,
                root,
                allow_existing_operation_dir=False,
            )
            layout.close()
            op_dirs_created.add(root_path)
    except StagingPlatformUnsupportedError as exc:
        result = CleanupResult(
            operation_id=operation_id,
            plan_id=plan.plan_id,
            mode=plan.mode,
            status=CleanupStatus.BLOCKED,
            targets=tuple(lock_results),
            warnings=(),
            errors=(PLATFORM_UNSUPPORTED, str(exc)),
        )
        return host._finalise_operation(
            handle_token=handle_token,
            session_id=session_id,
            result=result,
            operation_id=operation_id,
            mutation_started=False,
        )
    except StagingUnsafeError as exc:
        result = CleanupResult(
            operation_id=operation_id,
            plan_id=plan.plan_id,
            mode=plan.mode,
            status=CleanupStatus.FAILED_BEFORE_MUTATION,
            targets=tuple(lock_results),
            warnings=(),
            errors=(str(exc),),
        )
        return host._finalise_operation(
            handle_token=handle_token,
            session_id=session_id,
            result=result,
            operation_id=operation_id,
            mutation_started=False,
        )

    acc = ExecutionAccumulator(
        target_results=list(lock_results),
        lock_skips=len(skip_keys),
    )
    first_rename = True

    try:
        total = len(to_mutate)
        for index, target in enumerate(to_mutate, start=1):
            logger.info(
                "cleanup stage %d/%d %s/%s/%s",
                index,
                total,
                target.subject_type.value,
                target.subject_id,
                target.run_id,
            )
            if first_rename:
                fault_point("before_first_rename")
            outcome = host._stage_one(
                target, operation_id, plan, allow_existing_operation_dir=True
            )
            # Update mutation accounting BEFORE any post-rename hooks.
            if outcome.visible_removed:
                acc.note_visible_removed()
            if first_rename:
                if outcome.rename_attempted:
                    fault_point("after_first_rename")
                first_rename = False

            acc.append_target(outcome.target_result)
            acc.extend_warnings(outcome.warnings)
            acc.extend_errors(outcome.errors)
            if not outcome.visible_removed:
                logger.warning(
                    "cleanup stage skipped/failed %s/%s/%s status=%s %s",
                    target.subject_type.value,
                    target.subject_id,
                    target.run_id,
                    outcome.target_result.status.value,
                    outcome.target_result.message or "",
                )

            if outcome.deletion_ready:
                logger.info(
                    "cleanup delete %d/%d %s/%s/%s",
                    index,
                    total,
                    target.subject_type.value,
                    target.subject_id,
                    target.run_id,
                )
                fault_point("before_physical_verify")
                pd = host._physical_delete_one(
                    target,
                    Path(outcome.staging_path or ""),
                    operation_id,
                    staged_dev=outcome.staged_dev,
                    staged_ino=outcome.staged_ino,
                )
                fault_point("after_physical_verify")
                acc.target_results[-1] = pd
                if pd.status is TargetStatus.PHYSICAL_DELETED:
                    acc.note_physically_deleted()
                    logger.info(
                        "cleanup deleted %s/%s/%s",
                        target.subject_type.value,
                        target.subject_id,
                        target.run_id,
                    )
                    if "journal durability failed" in (pd.message or ""):
                        acc.journal_durability_failed = True
                        acc.errors.append(pd.message)
                    prune_msg = host._prune_subject_parent(target)
                    if prune_msg:
                        acc.warnings.append(prune_msg)
                        acc.append_target(
                            CleanupTargetResult(
                                subject_type=target.subject_type,
                                subject_id=target.subject_id,
                                run_id=target.run_id,
                                root_relative_path=target.root_relative_path,
                                canonical_path=target.canonical_path,
                                status=TargetStatus.PARENT_PRUNE_WARNING,
                                message=prune_msg,
                                filesystem_dev=target.filesystem_dev,
                                filesystem_ino=target.filesystem_ino,
                                root_kind=target.subject_type,
                            )
                        )
                elif pd.status is TargetStatus.PHYSICAL_DELETE_PARTIAL:
                    acc.has_staged_remnant = True
                    acc.errors.append(pd.message)
                    logger.error(
                        "cleanup partial delete %s/%s/%s: %s",
                        target.subject_type.value,
                        target.subject_id,
                        target.run_id,
                        pd.message,
                    )
                elif pd.status in {
                    TargetStatus.PHYSICAL_DELETE_FAILED,
                    TargetStatus.PHYSICAL_DELETE_REFUSED,
                }:
                    acc.has_staged_remnant = True
                    acc.errors.append(pd.message)
                    logger.error(
                        "cleanup delete failed %s/%s/%s status=%s: %s",
                        target.subject_type.value,
                        target.subject_id,
                        target.run_id,
                        pd.status.value,
                        pd.message,
                    )
            elif outcome.visible_removed:
                acc.has_staged_remnant = True
                logger.warning(
                    "cleanup staged but not deleted %s/%s/%s status=%s",
                    target.subject_type.value,
                    target.subject_id,
                    target.run_id,
                    outcome.target_result.status.value,
                )
    except StagingPlatformUnsupportedError as exc:
        if acc.mutation_started:
            acc.errors.append(f"{PLATFORM_UNSUPPORTED}: {exc}")
            acc.has_staged_remnant = True
        else:
            result = CleanupResult(
                operation_id=operation_id,
                plan_id=plan.plan_id,
                mode=plan.mode,
                status=CleanupStatus.BLOCKED,
                targets=tuple(acc.target_results),
                warnings=tuple(acc.warnings),
                errors=(PLATFORM_UNSUPPORTED, str(exc)),
            )
            return host._finalise_operation(
                handle_token=handle_token,
                session_id=session_id,
                result=result,
                operation_id=operation_id,
                mutation_started=False,
            )
    except Exception as exc:  # noqa: BLE001 — convert to PARTIAL after mutation
        if acc.mutation_started:
            acc.errors.append(f"post-mutation exception: {exc}")
            acc.has_staged_remnant = True
        else:
            result = CleanupResult(
                operation_id=operation_id,
                plan_id=plan.plan_id,
                mode=plan.mode,
                status=CleanupStatus.FAILED_BEFORE_MUTATION,
                targets=tuple(acc.target_results),
                warnings=tuple(acc.warnings),
                errors=(str(exc),),
            )
            return host._finalise_operation(
                handle_token=handle_token,
                session_id=session_id,
                result=result,
                operation_id=operation_id,
                mutation_started=False,
            )

    status = host._summarize_status(
        visible_removed=acc.visible_removed,
        physically_deleted=acc.physically_deleted,
        planned=len(to_mutate),
        lock_skips=acc.lock_skips,
        errors=acc.errors,
        has_staged_remnant=acc.has_staged_remnant,
        mutation_started=acc.mutation_started,
    )
    if acc.journal_durability_failed and status is CleanupStatus.SUCCESS:
        status = CleanupStatus.PARTIAL
    # Journal target vector can only downgrade SUCCESS (lock skips and
    # in-memory errors are not fully represented in journal targets).
    try:
        journal_status = host._status_from_loaded_operation(operation_id)
        if journal_status is CleanupStatus.PARTIAL and status is CleanupStatus.SUCCESS:
            status = CleanupStatus.PARTIAL
    except Exception:
        pass
    result = CleanupResult(
        operation_id=operation_id,
        plan_id=plan.plan_id,
        mode=plan.mode,
        status=status,
        targets=tuple(acc.target_results),
        warnings=tuple(acc.warnings),
        errors=tuple(acc.errors),
        visible_removed_count=acc.visible_removed,
        physically_deleted_count=acc.physically_deleted,
    )
    return host._finalise_operation(
        handle_token=handle_token,
        session_id=session_id,
        result=result,
        operation_id=operation_id,
        mutation_started=acc.mutation_started,
    )
