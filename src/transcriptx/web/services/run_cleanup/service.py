"""RunCleanupService — thin public façade over Phase A orchestration modules."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Mapping

from transcriptx.core.utils import paths as path_constants
from transcriptx.web.services.run_cleanup import deletion_phase
from transcriptx.web.services.run_cleanup import execution as execution_mod
from transcriptx.web.services.run_cleanup import finalization
from transcriptx.web.services.run_cleanup import journal_ops
from transcriptx.web.services.run_cleanup import locking
from transcriptx.web.services.run_cleanup import planning
from transcriptx.web.services.run_cleanup import recovery
from transcriptx.web.services.run_cleanup import results as results_mod
from transcriptx.web.services.run_cleanup import staging_phase
from transcriptx.web.services.run_cleanup.models import (
    CleanupAuthorization,
    CleanupMode,
    CleanupPlan,
    CleanupPreview,
    CleanupResult,
    CleanupStatus,
    CleanupTarget,
    RootIdentity,
    SubjectType,
)
from transcriptx.web.services.run_cleanup.root_validator import OutputRootValidator
from transcriptx.web.services.run_cleanup.runtime import CleanupRuntime
from transcriptx.web.services.run_cleanup.staging import (
    StagingUnsafeError,
)

CacheInvalidator = Callable[[], None]


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
        self._runtime = self._build_runtime()

    def _build_runtime(self) -> CleanupRuntime:
        """Private factory: public constructor signature stays frozen."""

        def _getter() -> Mapping[str, Path]:
            return self._protected_paths()

        from transcriptx.core.utils import run_writer_locks as locks_mod
        from transcriptx.core.utils.logger import get_logger

        return CleanupRuntime(
            outputs_dir=self.outputs_dir,
            group_outputs_dir=self.group_outputs_dir,
            state_dir=self.state_dir,
            project_root=self.project_root,
            data_dir=self.data_dir,
            config_dir=self.config_dir,
            protected_path_getter=_getter,
            cache_invalidator=self._cache_invalidator,
            lock_adapter=locks_mod,
            logger=get_logger(),
        )

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

    # --- temporary named shims (tests still call these privates) ---

    def _validate_roots(self) -> tuple[list[RootIdentity], list[str]]:
        return OutputRootValidator.validate(
            self.outputs_dir,
            self.group_outputs_dir,
            self._protected_paths(),
            project_root=self.project_root,
            data_dir=self.data_dir,
            state_dir=self.state_dir,
        )

    def _physical_delete_one(self, *args, **kwargs):
        return deletion_phase.physical_delete_one(self, *args, **kwargs)

    @staticmethod
    def _status_from_journal_targets(targets: list[dict]) -> CleanupStatus:
        return results_mod.status_from_journal_targets(targets)

    # --- public façade ---

    def preview_cleanup(
        self, mode: CleanupMode, session_id: str
    ) -> tuple[str, CleanupPreview]:
        return planning.preview_cleanup(self, mode, session_id)

    def execute_cleanup(
        self,
        handle_token: str,
        authorization: CleanupAuthorization,
        session_id: str,
    ) -> CleanupResult:
        return execution_mod.execute_cleanup(
            self, handle_token, authorization, session_id
        )

    def list_pending_staging(self) -> list[dict]:
        return self._runtime.journal.list_pending_staging(self.state_dir)  # type: ignore[attr-defined]

    def retry_interrupted_staging(self, operation_id: str) -> CleanupResult:
        return recovery.retry_interrupted_staging(self, operation_id)

    # --- internal delegates (host API for extracted modules) ---

    def _build_plan(self, mode: CleanupMode) -> CleanupPlan:
        return planning.build_plan(self, mode)

    def _result_on_gate_contention(self, *args, **kwargs):
        return execution_mod.result_on_gate_contention(self, *args, **kwargs)

    def _execute_under_gate(self, *args, **kwargs):
        return execution_mod.execute_under_gate(self, *args, **kwargs)

    def _execute_claimed(self, *args, **kwargs):
        return execution_mod.execute_claimed(self, *args, **kwargs)

    def _finalise_operation(self, *args, **kwargs):
        return finalization.finalise_operation(self, *args, **kwargs)

    def _persist_target_state(self, *args, **kwargs):
        return journal_ops.persist_target_state(self, *args, **kwargs)

    def _new_journaled_operation(self, *args, **kwargs):
        return journal_ops.new_journaled_operation(self, *args, **kwargs)

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

    def _acquire_locks(self, plan: CleanupPlan):
        return locking.acquire_locks(self, plan)

    @staticmethod
    def _release_locks(locks) -> None:
        locking.release_locks(locks)

    def _fd_walk_run_identity(self, root: RootIdentity, target: CleanupTarget) -> None:
        locking.fd_walk_run_identity(self, root, target)

    def _revalidate_execution_set_under_lock(self, plan, lock_results):
        return locking.revalidate_execution_set_under_lock(self, plan, lock_results)

    def _stage_one(self, *args, **kwargs):
        return staging_phase.stage_one(self, *args, **kwargs)

    def _prune_subject_parent(self, target: CleanupTarget):
        return deletion_phase.prune_subject_parent(self, target)

    def _invalidate_caches(self):
        return finalization.invalidate_caches(self)

    @staticmethod
    def _summarize_status(**kwargs) -> CleanupStatus:
        return results_mod.summarize_status(**kwargs)

    def _status_from_loaded_operation(self, operation_id: str) -> CleanupStatus:
        return results_mod.status_from_loaded_operation(self.state_dir, operation_id)

    def _reconcile_planned_or_started_target(self, **kwargs):
        return recovery.reconcile_planned_or_started_target(self, **kwargs)
