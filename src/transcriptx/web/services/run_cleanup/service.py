"""RunCleanupService — sole owner of bulk analysis-run cleanup."""

from __future__ import annotations

import errno
import os
import stat
from collections import defaultdict
from pathlib import Path
from typing import Callable, Mapping

from transcriptx.core.utils import paths as path_constants
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.run_writer_locks import (
    RunWriterLock,
    try_per_run_lock,
    try_run_tree_mutation_gate,
)
from transcriptx.web.services.run_cleanup import fd_ops
from transcriptx.web.services.run_cleanup import handles as handle_store
from transcriptx.web.services.run_cleanup import journal
from transcriptx.web.services.run_cleanup.execution_compare import (
    compare_with_lock_skip_masks,
)
from transcriptx.web.services.run_cleanup.faults import fault_point
from transcriptx.web.services.run_cleanup.fingerprint import (
    TreeFingerprintError,
    compute_tree_fingerprint,
)
from transcriptx.web.services.run_cleanup.models import (
    CLEANUP_BUSY,
    CLEANUP_POLICY_VERSION,
    JOURNAL_SCHEMA_VERSION,
    PLATFORM_UNSUPPORTED,
    CleanupAuthorization,
    CleanupMode,
    CleanupPlan,
    CleanupPreview,
    CleanupResult,
    CleanupStatus,
    CleanupTarget,
    CleanupTargetResult,
    EntryClassification,
    RootIdentity,
    StageOutcome,
    SubjectType,
    TargetStatus,
    authorization_is_valid,
    plan_to_preview,
)
from transcriptx.web.services.run_cleanup.physical_delete import (
    PhysicalDeletePartialError,
    PhysicalDeleteUnsafeError,
    safe_rmtree_verified,
    verify_staged_tree,
)
from transcriptx.web.services.run_cleanup.root_validator import OutputRootValidator
from transcriptx.web.services.run_cleanup.staging import (
    StagingPlatformUnsupportedError,
    StagingUnsafeError,
    ensure_secure_staging_directory,
    rename_into_staging,
)

CacheInvalidator = Callable[[], None]

logger = get_logger()


def default_protected_paths(
    *,
    project_root: Path | None = None,
    data_dir: Path | None = None,
    state_dir: Path | None = None,
    config_dir: Path | None = None,
) -> dict[str, Path]:
    data = Path(data_dir) if data_dir is not None else path_constants.DATA_DIR
    state = Path(state_dir) if state_dir is not None else path_constants.STATE_DIR
    config = Path(config_dir) if config_dir is not None else path_constants.CONFIG_DIR
    return {
        "transcripts": (
            path_constants.DIARISED_TRANSCRIPTS_DIR
            if data_dir is None
            else data / "transcripts"
        ),
        "recordings": (
            path_constants.RECORDINGS_DIR if data_dir is None else data / "recordings"
        ),
        "corrections": data / "corrections",
        "metadata": (
            path_constants.TRANSCRIPTS_METADATA_DIR
            if data_dir is None
            else data / "transcripts" / "metadata"
        ),
        "groups_defs": data / "groups",
        "config": config,
        "state": state,
        "preprocessing": data / "preprocessing",
        "wav_backup": data / "backups" / "wav",
    }


class RunCleanupService:
    """Discover, plan, authorize, stage, and delete analysis run directories."""

    def __init__(
        self,
        *,
        outputs_dir: Path | None = None,
        group_outputs_dir: Path | None = None,
        state_dir: Path | None = None,
        project_root: Path | None = None,
        data_dir: Path | None = None,
        config_dir: Path | None = None,
        protected_paths: Mapping[str, Path] | None = None,
        protected_path_getter: Callable[[], Mapping[str, Path]] | None = None,
        cache_invalidator: CacheInvalidator | None = None,
    ) -> None:
        self.outputs_dir = Path(
            outputs_dir if outputs_dir is not None else path_constants.OUTPUTS_DIR
        )
        self.group_outputs_dir = Path(
            group_outputs_dir
            if group_outputs_dir is not None
            else path_constants.GROUP_OUTPUTS_DIR
        )
        self.state_dir = Path(
            state_dir if state_dir is not None else path_constants.STATE_DIR
        )
        self.project_root = Path(
            project_root if project_root is not None else path_constants.PROJECT_ROOT
        )
        self.data_dir = Path(
            data_dir if data_dir is not None else path_constants.DATA_DIR
        )
        self.config_dir = Path(
            config_dir if config_dir is not None else path_constants.CONFIG_DIR
        )
        self._protected_paths_override = (
            dict(protected_paths) if protected_paths is not None else None
        )
        self._protected_path_getter = protected_path_getter
        self._cache_invalidator = cache_invalidator

    def _protected_paths(self) -> dict[str, Path]:
        if self._protected_path_getter is not None:
            return dict(self._protected_path_getter())
        if self._protected_paths_override is not None:
            return dict(self._protected_paths_override)
        return default_protected_paths(
            project_root=self.project_root,
            data_dir=self.data_dir,
            state_dir=self.state_dir,
            config_dir=self.config_dir,
        )

    def _validate_roots(self) -> tuple[list[RootIdentity], list[str]]:
        return OutputRootValidator.validate(
            self.outputs_dir,
            self.group_outputs_dir,
            self._protected_paths(),
            project_root=self.project_root,
            data_dir=self.data_dir,
            state_dir=self.state_dir,
        )

    def _build_plan(self, mode: CleanupMode) -> CleanupPlan:
        from transcriptx.web.services.run_cleanup.plan_builder import (
            build_execution_set,
            execution_set_to_plan,
        )

        roots, blocking = self._validate_roots()
        handle_store.invalidate_on_root_change(tuple(roots))
        handle_store.invalidate_on_policy_change(CLEANUP_POLICY_VERSION)
        es = build_execution_set(
            mode,
            roots,
            blocking,
            self.outputs_dir,
            self.group_outputs_dir,
        )
        return execution_set_to_plan(es)

    def preview_cleanup(
        self, mode: CleanupMode, session_id: str
    ) -> tuple[str, CleanupPreview]:
        logger.info("cleanup preview start mode=%s", mode.value)
        plan = self._build_plan(mode)
        # May raise HandleStoreFullError when capacity is exhausted by protected entries.
        token = handle_store.create_handle(plan, session_id)
        preview = plan_to_preview(plan)
        logger.info(
            "cleanup preview ready mode=%s plan_id=%s candidates=%d retained=%d "
            "can_execute=%s",
            mode.value,
            preview.plan_id,
            preview.run_count,
            len(preview.retained),
            preview.can_execute,
        )
        return token, preview

    def execute_cleanup(
        self,
        handle_token: str,
        authorization: CleanupAuthorization,
        session_id: str,
    ) -> CleanupResult:
        logger.info(
            "cleanup execute start mode=%s plan_id=%s",
            authorization.mode.value,
            authorization.plan_id,
        )
        gate = try_run_tree_mutation_gate(state_dir=self.state_dir)
        if gate is None:
            logger.warning("cleanup execute blocked: mutation gate busy")
            return self._result_on_gate_contention(
                handle_token, authorization, session_id
            )
        locks: list[RunWriterLock] = []
        try:
            result = self._execute_under_gate(
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
            self._release_locks(locks)
            gate.release()

    def _result_on_gate_contention(
        self,
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
                physically_deleted_count=(
                    prior.physically_deleted_count if prior else 0
                ),
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

    def _execute_under_gate(
        self,
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
            return self._execute_claimed(
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

    def _execute_claimed(
        self,
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
            logger.warning(
                "cleanup blocked: authorization failed plan_id=%s", plan.plan_id
            )
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

        rediscovered = self._build_plan(plan.mode)
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

        acquired, lock_results, lock_error = self._acquire_locks(plan)
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

        stale_results, rediscovery_status = self._revalidate_execution_set_under_lock(
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

        operation_id = self._new_journaled_operation(plan, to_mutate)
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
                root_path = str(self._output_root_for_target(target))
                if root_path in op_dirs_created:
                    continue
                root = self._planned_root_for_target(plan, target)
                layout = ensure_secure_staging_directory(
                    self._output_root_for_target(target),
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
            return self._finalise_operation(
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
            return self._finalise_operation(
                handle_token=handle_token,
                session_id=session_id,
                result=result,
                operation_id=operation_id,
                mutation_started=False,
            )

        target_results: list[CleanupTargetResult] = list(lock_results)
        visible_removed = 0
        physically_deleted = 0
        warnings: list[str] = []
        errors: list[str] = []
        mutation_started = False
        first_rename = True
        has_staged_remnant = False
        journal_durability_failed = False

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
                outcome = self._stage_one(
                    target, operation_id, plan, allow_existing_operation_dir=True
                )
                # Update mutation accounting BEFORE any post-rename hooks.
                if outcome.visible_removed:
                    mutation_started = True
                    visible_removed += 1
                if first_rename:
                    if outcome.rename_attempted:
                        fault_point("after_first_rename")
                    first_rename = False

                target_results.append(outcome.target_result)
                warnings.extend(outcome.warnings)
                errors.extend(outcome.errors)
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
                    pd = self._physical_delete_one(
                        target,
                        Path(outcome.staging_path or ""),
                        operation_id,
                        staged_dev=outcome.staged_dev,
                        staged_ino=outcome.staged_ino,
                    )
                    fault_point("after_physical_verify")
                    target_results[-1] = pd
                    if pd.status is TargetStatus.PHYSICAL_DELETED:
                        physically_deleted += 1
                        logger.info(
                            "cleanup deleted %s/%s/%s",
                            target.subject_type.value,
                            target.subject_id,
                            target.run_id,
                        )
                        if "journal durability failed" in (pd.message or ""):
                            journal_durability_failed = True
                            errors.append(pd.message)
                        prune_msg = self._prune_subject_parent(target)
                        if prune_msg:
                            warnings.append(prune_msg)
                            target_results.append(
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
                        has_staged_remnant = True
                        errors.append(pd.message)
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
                        has_staged_remnant = True
                        errors.append(pd.message)
                        logger.error(
                            "cleanup delete failed %s/%s/%s status=%s: %s",
                            target.subject_type.value,
                            target.subject_id,
                            target.run_id,
                            pd.status.value,
                            pd.message,
                        )
                elif outcome.visible_removed:
                    has_staged_remnant = True
                    logger.warning(
                        "cleanup staged but not deleted %s/%s/%s status=%s",
                        target.subject_type.value,
                        target.subject_id,
                        target.run_id,
                        outcome.target_result.status.value,
                    )
        except StagingPlatformUnsupportedError as exc:
            if mutation_started:
                errors.append(f"{PLATFORM_UNSUPPORTED}: {exc}")
                has_staged_remnant = True
            else:
                result = CleanupResult(
                    operation_id=operation_id,
                    plan_id=plan.plan_id,
                    mode=plan.mode,
                    status=CleanupStatus.BLOCKED,
                    targets=tuple(target_results),
                    warnings=tuple(warnings),
                    errors=(PLATFORM_UNSUPPORTED, str(exc)),
                )
                return self._finalise_operation(
                    handle_token=handle_token,
                    session_id=session_id,
                    result=result,
                    operation_id=operation_id,
                    mutation_started=False,
                )
        except Exception as exc:  # noqa: BLE001 — convert to PARTIAL after mutation
            if mutation_started:
                errors.append(f"post-mutation exception: {exc}")
                has_staged_remnant = True
            else:
                result = CleanupResult(
                    operation_id=operation_id,
                    plan_id=plan.plan_id,
                    mode=plan.mode,
                    status=CleanupStatus.FAILED_BEFORE_MUTATION,
                    targets=tuple(target_results),
                    warnings=tuple(warnings),
                    errors=(str(exc),),
                )
                return self._finalise_operation(
                    handle_token=handle_token,
                    session_id=session_id,
                    result=result,
                    operation_id=operation_id,
                    mutation_started=False,
                )

        status = self._summarize_status(
            visible_removed=visible_removed,
            physically_deleted=physically_deleted,
            planned=len(to_mutate),
            lock_skips=len(skip_keys),
            errors=errors,
            has_staged_remnant=has_staged_remnant,
            mutation_started=mutation_started,
        )
        if journal_durability_failed and status is CleanupStatus.SUCCESS:
            status = CleanupStatus.PARTIAL
        # Journal target vector can only downgrade SUCCESS (lock skips and
        # in-memory errors are not fully represented in journal targets).
        try:
            journal_status = self._status_from_loaded_operation(operation_id)
            if (
                journal_status is CleanupStatus.PARTIAL
                and status is CleanupStatus.SUCCESS
            ):
                status = CleanupStatus.PARTIAL
        except Exception:
            pass
        result = CleanupResult(
            operation_id=operation_id,
            plan_id=plan.plan_id,
            mode=plan.mode,
            status=status,
            targets=tuple(target_results),
            warnings=tuple(warnings),
            errors=tuple(errors),
            visible_removed_count=visible_removed,
            physically_deleted_count=physically_deleted,
        )
        return self._finalise_operation(
            handle_token=handle_token,
            session_id=session_id,
            result=result,
            operation_id=operation_id,
            mutation_started=mutation_started,
        )

    def _finalise_operation(
        self,
        *,
        handle_token: str,
        session_id: str,
        result: CleanupResult,
        operation_id: str,
        mutation_started: bool,
    ) -> CleanupResult:
        """Phase-aware finalisation: never raises; always best-effort through all steps."""
        warnings = list(result.warnings)
        errors = list(result.errors)
        status = result.status
        # 1. Cache invalidation when mutation started (even if later steps fail)
        try:
            if mutation_started:
                fault_point("before_cache_invalidation")
                for w in self._invalidate_caches():
                    warnings.append(w)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"cache invalidation failed: {exc}")
        # 2. Terminal journal update (may be absent when no journal created)
        try:
            if operation_id:
                fault_point("before_terminal_journal")
                # Never write SUCCESS if journal durability cannot be confirmed.
                write_status = status
                if status is CleanupStatus.SUCCESS:
                    # Re-check target vector immediately before terminal write.
                    try:
                        derived = self._status_from_loaded_operation(operation_id)
                        if derived is not CleanupStatus.SUCCESS:
                            write_status = derived
                            status = derived
                    except Exception as exc:  # noqa: BLE001
                        write_status = CleanupStatus.PARTIAL
                        status = CleanupStatus.PARTIAL
                        errors.append(f"could not derive terminal status: {exc}")
                dur = journal.update_operation_status(
                    self.state_dir, operation_id, write_status.value
                )
                if dur.outcome is journal.DirFsyncOutcome.FAILED:
                    errors.append(f"terminal journal durability failed: {dur.message}")
                    if status is CleanupStatus.SUCCESS:
                        status = CleanupStatus.PARTIAL
        except Exception as exc:  # noqa: BLE001
            errors.append(f"terminal journal update failed: {exc}")
            if status is CleanupStatus.SUCCESS:
                status = CleanupStatus.PARTIAL
        final = CleanupResult(
            operation_id=result.operation_id,
            plan_id=result.plan_id,
            mode=result.mode,
            status=status,
            targets=result.targets,
            warnings=tuple(warnings),
            errors=tuple(errors),
            visible_removed_count=result.visible_removed_count,
            physically_deleted_count=result.physically_deleted_count,
        )
        # 3. Handle completion — on failure leave claimed/in_progress (never re-issue)
        try:
            fault_point("before_terminal_result_store")
            handle_store.store_result(handle_token, session_id, final)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"handle result store failed: {exc}")
            final = CleanupResult(
                operation_id=final.operation_id,
                plan_id=final.plan_id,
                mode=final.mode,
                status=final.status,
                targets=final.targets,
                warnings=tuple(warnings),
                errors=final.errors,
                visible_removed_count=final.visible_removed_count,
                physically_deleted_count=final.physically_deleted_count,
            )
        return final

    def _persist_target_state(
        self,
        operation_id: str,
        *,
        canonical_path: str,
        state: str,
        staging_path: str | None = None,
        staged_dev: int | None = None,
        staged_ino: int | None = None,
        extra: Mapping[str, object] | None = None,
        require_durable: bool = False,
    ) -> journal.DirFsyncResult | None:
        """Best-effort journal target update. Returns None on hard failure."""
        try:
            dur = journal.update_target_state(
                self.state_dir,
                operation_id,
                canonical_path=canonical_path,
                state=state,
                staging_path=staging_path,
                staged_dev=staged_dev,
                staged_ino=staged_ino,
                extra=extra,
            )
        except Exception:
            if require_durable:
                raise
            return None
        if require_durable and dur.outcome is journal.DirFsyncOutcome.FAILED:
            raise journal.JournalDurabilityError(dur.message or "journal fsync failed")
        return dur

    def _new_journaled_operation(
        self, plan: CleanupPlan, to_mutate: list[CleanupTarget]
    ) -> str:
        staging_map: dict[str, str] = {}
        for t in to_mutate:
            staging_map[t.canonical_path] = str(
                journal.intended_staging_path(
                    self._output_root_for_target(t), "0_000000000000", t
                )
            )
        # placeholder replaced below after op id known
        last_exc: Exception | None = None
        for _ in range(5):
            operation_id = journal.new_operation_id()
            staging_map = {
                t.canonical_path: str(
                    journal.intended_staging_path(
                        self._output_root_for_target(t), operation_id, t
                    )
                )
                for t in to_mutate
            }
            try:
                journal.write_operation(
                    self.state_dir,
                    operation_id=operation_id,
                    plan=CleanupPlan(
                        plan_id=plan.plan_id,
                        mode=plan.mode,
                        policy_version=plan.policy_version,
                        created_at_iso=plan.created_at_iso,
                        roots=plan.roots,
                        candidates=tuple(to_mutate),
                        retained=plan.retained,
                        exclusions=plan.exclusions,
                        warnings=plan.warnings,
                        blocking_errors=plan.blocking_errors,
                        can_execute=plan.can_execute,
                    ),
                    staging_destinations=staging_map,
                )
                return operation_id
            except FileExistsError as exc:
                last_exc = exc
                continue
        raise RuntimeError(f"could not allocate operation_id: {last_exc}")

    def _output_root_for_target(self, target: CleanupTarget) -> Path:
        if target.subject_type is SubjectType.group:
            return self.group_outputs_dir
        return self.outputs_dir

    def _planned_root_for_target(
        self, plan: CleanupPlan, target: CleanupTarget
    ) -> RootIdentity:
        kind = target.subject_type
        for r in plan.roots:
            if r.kind is kind:
                return r
        raise StagingUnsafeError(f"no planned root for {kind}")

    def _acquire_locks(
        self, plan: CleanupPlan
    ) -> tuple[list[RunWriterLock], list[CleanupTargetResult], str | None]:
        results: list[CleanupTargetResult] = []
        locks: list[RunWriterLock] = []
        if plan.mode is CleanupMode.DELETE_ALL:
            ordered = sorted(plan.candidates, key=lambda t: t.canonical_path)
            for target in ordered:
                fault_point("before_per_run_lock")
                lock = try_per_run_lock(target.canonical_path, state_dir=self.state_dir)
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
        candidate_ids = {
            (c.subject_type, c.subject_id, c.run_id) for c in plan.candidates
        }
        for target in ordered:
            subject_key = (target.subject_type, target.subject_id)
            if subject_key in subject_failed:
                continue
            fault_point("before_per_run_lock")
            lock = try_per_run_lock(target.canonical_path, state_dir=self.state_dir)
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

    @staticmethod
    def _release_locks(locks: list[RunWriterLock]) -> None:
        for lock in reversed(locks):
            try:
                lock.release()
            except Exception:
                pass

    def _fd_walk_run_identity(self, root: RootIdentity, target: CleanupTarget) -> None:
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

    def _revalidate_execution_set_under_lock(
        self,
        plan: CleanupPlan,
        lock_results: list[CleanupTargetResult],
    ) -> tuple[list[CleanupTargetResult], CleanupStatus | None]:
        from transcriptx.web.services.run_cleanup.plan_builder import (
            build_execution_set,
        )

        results: list[CleanupTargetResult] = list(lock_results)
        roots, blocking = self._validate_roots()
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
            self.outputs_dir,
            self.group_outputs_dir,
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
            root = self._planned_root_for_target(plan, target)
            try:
                self._fd_walk_run_identity(root, target)
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

    def _stage_one(
        self,
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
            self._persist_target_state(
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
            root = self._planned_root_for_target(plan, target)
            layout = ensure_secure_staging_directory(
                self._output_root_for_target(target),
                operation_id,
                target,
                root,
                allow_existing_operation_dir=allow_existing_operation_dir,
            )
            staging_path = str(layout.staging_dest)
            basename = layout.basename
            # Durable intent before rename — crash after this is recoverable.
            self._persist_target_state(
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
            self._persist_target_state(
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
                raise StagingUnsafeError(
                    "staging layout unavailable for post-rename proof"
                )
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
                self.state_dir,
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
            self._persist_target_state(
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

    def _physical_delete_one(
        self,
        target: CleanupTarget,
        staging_dest: Path,
        operation_id: str,
        *,
        staged_dev: int | None = None,
        staged_ino: int | None = None,
        require_fingerprint: bool = True,
    ) -> CleanupTargetResult:
        if not journal.is_journal_recognised_staging_path(
            self.state_dir,
            staging_dest,
            operation_id=operation_id,
            subject_type=target.subject_type.value,
            subject_id=target.subject_id,
            run_id=target.run_id,
            canonical_path=target.canonical_path,
            outputs_dir=self.outputs_dir,
            group_outputs_dir=self.group_outputs_dir,
        ):
            self._persist_target_state(
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
            self._persist_target_state(
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
                    self.state_dir,
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
            self._persist_target_state(
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
            self._persist_target_state(
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
            self._persist_target_state(
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
            self._persist_target_state(
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

    def _prune_subject_parent(self, target: CleanupTarget) -> str | None:
        subject_parent = Path(target.canonical_path).parent
        try:
            st = subject_parent.lstat()
            if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
                return f"subject parent unsafe to prune: {subject_parent}"
            for root in (self.outputs_dir, self.group_outputs_dir):
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

    def _invalidate_caches(self) -> list[str]:
        warnings: list[str] = []
        if self._cache_invalidator is not None:
            try:
                self._cache_invalidator()
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"cache invalidation failed: {exc}")
            return warnings
        try:
            from transcriptx.web.services.artifact_service import clear_artifact_caches

            clear_artifact_caches()
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"artifact cache invalidation failed: {exc}")
        try:
            from transcriptx.web.cache_helpers import clear_run_listing_caches

            clear_run_listing_caches()
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"run listing cache invalidation failed: {exc}")
        return warnings

    @staticmethod
    def _summarize_status(
        *,
        visible_removed: int,
        physically_deleted: int,
        planned: int,
        lock_skips: int,
        errors: list[str],
        has_staged_remnant: bool,
        mutation_started: bool,
    ) -> CleanupStatus:
        if mutation_started:
            if (
                visible_removed == planned
                and physically_deleted == planned
                and not errors
                and not lock_skips
                and not has_staged_remnant
            ):
                return CleanupStatus.SUCCESS
            return CleanupStatus.PARTIAL
        if lock_skips:
            return CleanupStatus.PARTIAL
        if errors:
            return CleanupStatus.FAILED_BEFORE_MUTATION
        return CleanupStatus.NOOP

    @staticmethod
    def _status_from_journal_targets(targets: list[dict]) -> CleanupStatus:
        """Derive operation status from the complete journal target-state vector."""
        if not targets:
            return CleanupStatus.NOOP
        states = [str(t.get("state") or "") for t in targets]
        success = journal.TERMINAL_SUCCESS_TARGET_STATES
        skip = journal.TERMINAL_SKIP_TARGET_STATES
        # Mid-flight / remnant states (planned alone means rename never happened).
        mid_flight = journal.PENDING_TARGET_STATES - {"planned"}
        if any(s in mid_flight for s in states):
            return CleanupStatus.PARTIAL
        if any(s == "planned" for s in states):
            if any(s in success for s in states):
                return CleanupStatus.PARTIAL
            return CleanupStatus.FAILED_BEFORE_MUTATION
        if any(s not in success | skip for s in states):
            return CleanupStatus.PARTIAL
        if any(s in success for s in states):
            return CleanupStatus.SUCCESS
        return CleanupStatus.NOOP

    def _status_from_loaded_operation(self, operation_id: str) -> CleanupStatus:
        data = journal.load_operation(
            self.state_dir,
            operation_id,
            expected_policy_version=CLEANUP_POLICY_VERSION,
            expected_schema_version=JOURNAL_SCHEMA_VERSION,
        )
        if data is None:
            raise FileNotFoundError(f"cleanup journal missing: {operation_id}")
        return self._status_from_journal_targets(list(data.get("targets") or []))

    def list_pending_staging(self) -> list[dict]:
        """Public wrapper over journal pending-staging discovery."""
        return journal.list_pending_staging(self.state_dir)

    def _reconcile_planned_or_started_target(
        self,
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
                    self._persist_target_state(
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
            self._persist_target_state(
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

    def retry_interrupted_staging(self, operation_id: str) -> CleanupResult:
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
        gate = try_run_tree_mutation_gate(state_dir=self.state_dir)
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
                self.state_dir,
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
                claim_dur = journal.claim_retry_ownership(self.state_dir, operation_id)
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
            roots, blocking = self._validate_roots()
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
                    self._output_root_for_target(fake), operation_id, fake
                )
                # Acquire run lock BEFORE any staged-tree verification
                run_lock = try_per_run_lock(
                    fake.canonical_path, state_dir=self.state_dir
                )
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
                    self._persist_target_state(
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
                    reconciled = self._reconcile_planned_or_started_target(
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
                            self._persist_target_state(
                                operation_id,
                                canonical_path=fake.canonical_path,
                                state="recovered_from_incomplete_stage",
                                staging_path=str(staging_path),
                                staged_dev=staged_dev,
                                staged_ino=staged_ino,
                            )
                    except OSError:
                        pass
                tr = self._physical_delete_one(
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
                for w in self._invalidate_caches():
                    warnings.append(w)
            # Authoritative status from complete journal target vector
            try:
                status = self._status_from_loaded_operation(operation_id)
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
                    self.state_dir, operation_id, status.value
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
            self._release_locks(locks)
            gate.release()
