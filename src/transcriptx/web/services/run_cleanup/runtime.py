"""Static configuration and late-binding dependency adapters for cleanup."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, runtime_checkable

from transcriptx.web.services.run_cleanup import faults as faults_mod
from transcriptx.web.services.run_cleanup import handles as handle_store
from transcriptx.web.services.run_cleanup import journal as journal_mod

CacheInvalidator = Callable[[], None]
ProtectedPathGetter = Callable[[], Mapping[str, Path]]


@runtime_checkable
class HandleStoreProtocol(Protocol):
    def create_handle(self, plan: object, session_id: str) -> str: ...

    def claim_handle(self, handle_token: str, session_id: str) -> object: ...

    def store_result(
        self, handle_token: str, session_id: str, result: object
    ) -> None: ...

    def peek_handle(self, handle_token: str, session_id: str) -> object: ...

    def invalidate_on_root_change(self, roots: object) -> None: ...

    def invalidate_on_policy_change(self, policy_version: int) -> None: ...


@runtime_checkable
class JournalAdapterProtocol(Protocol):
    def write_operation(self, *args: object, **kwargs: object) -> object: ...

    def update_target_state(self, *args: object, **kwargs: object) -> object: ...

    def update_operation_status(self, *args: object, **kwargs: object) -> object: ...

    def list_pending_staging(self, state_dir: Path) -> list: ...

    def load_operation_typed(self, *args: object, **kwargs: object) -> object: ...

    def claim_retry_ownership(self, *args: object, **kwargs: object) -> object: ...

    def new_operation_id(self) -> str: ...

    def intended_staging_path(self, *args: object, **kwargs: object) -> Path: ...

    def validate_operation_id(self, operation_id: str) -> str: ...


@runtime_checkable
class LockAdapterProtocol(Protocol):
    def try_run_tree_mutation_gate(self, *, state_dir: Path | None = None) -> Any: ...

    def try_per_run_lock(
        self, canonical_run_root: object, *, state_dir: Path | None = None
    ) -> Any: ...


@runtime_checkable
class CacheInvalidatorProtocol(Protocol):
    def invalidate(self) -> list[str]: ...


@runtime_checkable
class LoggerProtocol(Protocol):
    def info(self, msg: str, *args: object) -> None: ...

    def warning(self, msg: str, *args: object) -> None: ...

    def error(self, msg: str, *args: object) -> None: ...


@runtime_checkable
class FaultInjectorProtocol(Protocol):
    def fault_point(self, name: str) -> None: ...


@runtime_checkable
class ProtectedPathProviderProtocol(Protocol):
    def protected_paths(self) -> dict[str, Path]: ...


@dataclass(frozen=True)
class CleanupRuntime:
    """Immutable static config + dependency adapters.

    Validated RootIdentity values and rediscovered execution sets are
    *per-operation* and must live on ExecutionContext / planning results —
    never cached here across calls.

    Adapters hold **module objects** (late-binding) so test monkeypatches
    on those modules remain effective at call time.
    """

    outputs_dir: Path
    group_outputs_dir: Path
    state_dir: Path
    project_root: Path
    data_dir: Path
    config_dir: Path
    protected_path_getter: ProtectedPathGetter
    cache_invalidator: CacheInvalidator | None
    # Late-binding: hold module objects so test monkeypatches remain effective.
    handle_store: object = handle_store
    journal: object = journal_mod
    fault_injector: object = faults_mod
    lock_adapter: object | None = None
    logger: logging.Logger | None = None

    def protected_paths(self) -> dict[str, Path]:
        return dict(self.protected_path_getter())

    def fault_point(self, name: str) -> None:
        self.fault_injector.fault_point(name)  # type: ignore[attr-defined]

    def log(self) -> logging.Logger:
        if self.logger is not None:
            return self.logger
        from transcriptx.core.utils.logger import get_logger

        return get_logger()
