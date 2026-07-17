"""RunCleanupService — thin public façade over Phase A orchestration modules."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Mapping

from transcriptx.core.utils import paths as path_constants
from transcriptx.web.services.run_cleanup import execution as execution_mod
from transcriptx.web.services.run_cleanup import journal as journal_mod
from transcriptx.web.services.run_cleanup import planning
from transcriptx.web.services.run_cleanup import recovery
from transcriptx.web.services.run_cleanup.models import (
    CleanupAuthorization,
    CleanupMode,
    CleanupPreview,
    CleanupResult,
)
from transcriptx.web.services.run_cleanup.runtime import CleanupRuntime

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
        return journal_mod.list_pending_staging(self.state_dir)

    def retry_interrupted_staging(self, operation_id: str) -> CleanupResult:
        return recovery.retry_interrupted_staging(self, operation_id)
