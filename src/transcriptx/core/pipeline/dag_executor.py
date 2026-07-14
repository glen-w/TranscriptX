"""DAG executor state machine for ordered module runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from transcriptx.core.pipeline.contracts import ErrorKind, ExecutionPlan, ModuleOutcome


@dataclass
class ExecutorState:
    module_results: Dict[str, Any] = field(default_factory=dict)
    modules_run: List[str] = field(default_factory=list)
    skipped_modules: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    cache_hits: List[str] = field(default_factory=list)
    outcomes: List[ModuleOutcome] = field(default_factory=list)


class DAGExecutor:
    """Run-local state owner; no persistence/reporting/logging side effects."""

    def reduce_outcome(
        self,
        state: ExecutorState,
        module_name: str,
        outcome: ModuleOutcome,
        *,
        module_result: Optional[Dict[str, Any]] = None,
    ) -> ExecutorState:
        state.outcomes.append(outcome)
        if outcome.status == "succeeded":
            state.modules_run.append(module_name)
            if module_result is not None:
                state.module_results[module_name] = module_result
            return state
        if outcome.status in {"skipped", "blocked"}:
            state.skipped_modules.append(
                {
                    "module": module_name,
                    "reason": outcome.reason or "",
                    "execution_status": outcome.status,
                    "blocking_modules": outcome.blocking_modules,
                }
            )
            return state
        if outcome.status in {"failed", "aborted"}:
            if outcome.reason:
                state.errors.append(outcome.reason)
            elif outcome.error_kind:
                state.errors.append(f"{outcome.error_kind.value}:{module_name}")
            else:
                state.errors.append(f"module_failed:{module_name}")
            if module_result is not None:
                state.module_results[module_name] = module_result
            return state
        return state

    def outcome_from_legacy(
        self,
        module_name: str,
        *,
        legacy_status: str,
        error: Optional[str] = None,
        skip_reason: Optional[str] = None,
        blocking_modules: Optional[List[str]] = None,
        duration_ms: float = 0.0,
    ) -> ModuleOutcome:
        if legacy_status == "success":
            return ModuleOutcome(
                module=module_name, status="succeeded", duration_ms=duration_ms
            )
        if legacy_status == "skipped":
            return ModuleOutcome(
                module=module_name,
                status="skipped",
                reason=skip_reason,
                duration_ms=duration_ms,
            )
        if legacy_status == "blocked":
            return ModuleOutcome(
                module=module_name,
                status="blocked",
                reason=skip_reason,
                blocking_modules=blocking_modules or [],
                duration_ms=duration_ms,
            )
        return ModuleOutcome(
            module=module_name,
            status="failed",
            reason=error or "module execution failed",
            error_kind=ErrorKind.EXECUTION,
            duration_ms=duration_ms,
        )

    def blocked_from_plan(self, plan: ExecutionPlan) -> List[ModuleOutcome]:
        outcomes: List[ModuleOutcome] = []
        for module_name, blockers in sorted(plan.blocked.items()):
            outcomes.append(
                ModuleOutcome(
                    module=module_name,
                    status="blocked",
                    reason="blocked_in_planner",
                    error_kind=ErrorKind.DEPENDENCY,
                    blocking_modules=list(blockers),
                )
            )
        return outcomes
