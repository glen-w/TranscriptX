"""Unit tests for DAGExecutor reduce/legacy/blocked outcome vocabulary."""

from __future__ import annotations

import pytest

from transcriptx.core.pipeline.contracts import (
    ErrorKind,
    ExecutionPlan,
    ModuleOutcome,
    SCHEMA_VERSION,
)
from transcriptx.core.pipeline.dag_executor import DAGExecutor, ExecutorState


@pytest.fixture
def executor() -> DAGExecutor:
    return DAGExecutor()


@pytest.mark.unit
def test_reduce_outcome_succeeded_records_result(executor: DAGExecutor) -> None:
    state = ExecutorState()
    outcome = ModuleOutcome(module="stats", status="succeeded", duration_ms=1.5)
    executor.reduce_outcome(state, "stats", outcome, module_result={"ok": True})
    assert state.modules_run == ["stats"]
    assert state.module_results["stats"] == {"ok": True}
    assert state.outcomes == [outcome]


@pytest.mark.unit
def test_reduce_outcome_skipped_and_blocked(executor: DAGExecutor) -> None:
    state = ExecutorState()
    executor.reduce_outcome(
        state,
        "acts",
        ModuleOutcome(module="acts", status="skipped", reason="gate"),
    )
    executor.reduce_outcome(
        state,
        "ner",
        ModuleOutcome(
            module="ner",
            status="blocked",
            reason="deps",
            blocking_modules=["acts"],
        ),
    )
    assert state.modules_run == []
    assert state.skipped_modules == [
        {
            "module": "acts",
            "reason": "gate",
            "execution_status": "skipped",
            "blocking_modules": [],
        },
        {
            "module": "ner",
            "reason": "deps",
            "execution_status": "blocked",
            "blocking_modules": ["acts"],
        },
    ]


@pytest.mark.unit
@pytest.mark.parametrize(
    "outcome,expected_error",
    [
        (
            ModuleOutcome(module="m", status="failed", reason="boom"),
            "boom",
        ),
        (
            ModuleOutcome(
                module="m",
                status="failed",
                error_kind=ErrorKind.EXECUTION,
            ),
            "execution:m",
        ),
        (
            ModuleOutcome(module="m", status="aborted"),
            "module_failed:m",
        ),
    ],
)
def test_reduce_outcome_failed_error_vocabulary(
    executor: DAGExecutor,
    outcome: ModuleOutcome,
    expected_error: str,
) -> None:
    state = ExecutorState()
    executor.reduce_outcome(state, "m", outcome, module_result={"status": "failed"})
    assert state.errors == [expected_error]
    assert state.module_results["m"] == {"status": "failed"}
    assert "m" not in state.modules_run


@pytest.mark.unit
def test_reduce_outcome_unknown_status_is_noop_aside_from_append(
    executor: DAGExecutor,
) -> None:
    state = ExecutorState()
    # Intentionally bypass Literal typing to cover the fall-through branch.
    outcome = ModuleOutcome(module="x", status="succeeded")
    object.__setattr__(outcome, "status", "unknown")  # type: ignore[misc]
    executor.reduce_outcome(state, "x", outcome)
    assert state.outcomes == [outcome]
    assert state.modules_run == []
    assert state.skipped_modules == []
    assert state.errors == []


@pytest.mark.unit
def test_outcome_from_legacy_maps_statuses(executor: DAGExecutor) -> None:
    assert (
        executor.outcome_from_legacy("a", legacy_status="success").status == "succeeded"
    )
    skipped = executor.outcome_from_legacy(
        "b", legacy_status="skipped", skip_reason="preflight"
    )
    assert skipped.status == "skipped"
    assert skipped.reason == "preflight"
    blocked = executor.outcome_from_legacy(
        "c",
        legacy_status="blocked",
        skip_reason="deps",
        blocking_modules=["a"],
    )
    assert blocked.status == "blocked"
    assert blocked.blocking_modules == ["a"]
    failed = executor.outcome_from_legacy(
        "d", legacy_status="failed", error="kaboom", duration_ms=9.0
    )
    assert failed.status == "failed"
    assert failed.reason == "kaboom"
    assert failed.error_kind == ErrorKind.EXECUTION
    assert failed.duration_ms == 9.0
    default_failed = executor.outcome_from_legacy("e", legacy_status="other")
    assert default_failed.reason == "module execution failed"


@pytest.mark.unit
def test_blocked_from_plan_sorted_deterministic(executor: DAGExecutor) -> None:
    plan = ExecutionPlan(
        requested=["z", "a"],
        runnable=[],
        dependency_added=[],
        blocked={"z": ["dep"], "a": ["x", "y"]},
        skipped_preflight=[],
        deterministic_order=[],
        plan_hash="h",
        schema_version=SCHEMA_VERSION,
    )
    outcomes = executor.blocked_from_plan(plan)
    assert [o.module for o in outcomes] == ["a", "z"]
    assert all(o.status == "blocked" for o in outcomes)
    assert all(o.error_kind == ErrorKind.DEPENDENCY for o in outcomes)
    assert outcomes[0].blocking_modules == ["x", "y"]
    assert outcomes[0].reason == "blocked_in_planner"
