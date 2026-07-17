"""Static configuration and late-binding dependency adapters for cleanup."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Protocol, runtime_checkable

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


@runtime_checkable
class JournalAdapterProtocol(Protocol):
    def write_operation(self, *args: object, **kwargs: object) -> object: ...

    def update_target_state(self, *args: object, **kwargs: object) -> object: ...

    def update_operation_status(self, *args: object, **kwargs: object) -> object: ...


@runtime_checkable
class FaultInjectorProtocol(Protocol):
    def fault_point(self, name: str) -> None: ...


@dataclass(frozen=True)
class CleanupRuntime:
    """Immutable static config + dependency adapters.

    Validated RootIdentity values and rediscovered execution sets are
    *per-operation* and must live on ExecutionContext / planning results —
    never cached here across calls.
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

    def protected_paths(self) -> dict[str, Path]:
        return dict(self.protected_path_getter())

    def fault_point(self, name: str) -> None:
        self.fault_injector.fault_point(name)  # type: ignore[attr-defined]
