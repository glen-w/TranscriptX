"""Per-operation immutable context and single-writer accumulator."""

from __future__ import annotations

from dataclasses import dataclass, field

from transcriptx.web.services.run_cleanup.models import (
    CleanupMode,
    CleanupPlan,
    CleanupTargetResult,
    RootIdentity,
)


@dataclass(frozen=True)
class ExecutionContext:
    """Immutable per-operation metadata (not a cache of rediscovery)."""

    operation_id: str
    mode: CleanupMode
    plan_id: str
    session_id: str
    handle_token: str
    plan: CleanupPlan
    validated_roots: tuple[RootIdentity, ...]


@dataclass
class ExecutionAccumulator:
    """Deliberately mutable accounting; single-writer owned by execution/recovery.

    Phase helpers must return structured outcomes and must not maintain
    parallel counters or flags.
    """

    mutation_started: bool = False
    visible_removed: int = 0
    physically_deleted: int = 0
    has_staged_remnant: bool = False
    journal_durability_failed: bool = False
    target_results: list[CleanupTargetResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    lock_skips: int = 0

    def note_visible_removed(self, n: int = 1) -> None:
        self.visible_removed += n
        self.mutation_started = True

    def note_physically_deleted(self, n: int = 1) -> None:
        self.physically_deleted += n

    def append_target(self, result: CleanupTargetResult) -> None:
        self.target_results.append(result)

    def extend_warnings(self, items: list[str] | tuple[str, ...]) -> None:
        self.warnings.extend(items)

    def extend_errors(self, items: list[str] | tuple[str, ...]) -> None:
        self.errors.extend(items)
