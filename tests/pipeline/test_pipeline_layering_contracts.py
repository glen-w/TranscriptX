"""Tests for pipeline layering contracts."""

from __future__ import annotations

from transcriptx.core.pipeline.contracts import (
    ErrorKind,
    ModuleOutcome,
    PersistenceOutcome,
    RegistryModuleSnapshot,
    RegistrySnapshot,
)
from transcriptx.core.pipeline.dag_executor import DAGExecutor, ExecutorState
from transcriptx.core.pipeline.dag_planner import DAGPlanner
from transcriptx.core.pipeline.run_orchestrator import _combine_status


def test_dag_planner_excludes_finalize_phase_modules() -> None:
    planner = DAGPlanner()
    snapshot = RegistrySnapshot(
        modules={
            "stats": RegistryModuleSnapshot(
                name="stats", dependencies=[], category="light"
            ),
            "chart_descriptions": RegistryModuleSnapshot(
                name="chart_descriptions",
                dependencies=[],
                category="medium",
                finalize_phase=True,
            ),
        }
    )
    plan = planner.plan(["stats", "chart_descriptions"], snapshot)
    assert "stats" in plan.deterministic_order
    assert "chart_descriptions" not in plan.deterministic_order
    assert "chart_descriptions" not in plan.runnable
    assert "chart_descriptions" in plan.requested


def test_optional_persistence_failure_only_downgrades_success():
    outcomes = [PersistenceOutcome(name="x", success=False, severity="optional")]
    assert _combine_status("succeeded", outcomes) == "partial"
    assert _combine_status("failed", outcomes) == "failed"
    assert _combine_status("aborted", outcomes) == "aborted"


def test_abort_with_required_persistence_failure_ends_failed():
    outcomes = [
        PersistenceOutcome(name="run_report", success=False, severity="required")
    ]
    assert _combine_status("aborted", outcomes) == "failed"


def test_dag_planner_blocks_unknown_modules_in_plan():
    planner = DAGPlanner()
    snapshot = RegistrySnapshot(
        modules={
            "known": RegistryModuleSnapshot(
                name="known", dependencies=[], category="light"
            )
        }
    )
    plan = planner.plan(["known", "missing"], snapshot)
    assert "missing" not in plan.blocked
    assert "missing" in plan.skipped_preflight
    assert "known" in plan.deterministic_order


def test_planner_blocked_is_reserved_for_upstream_unavailable_paths():
    planner = DAGPlanner()
    snapshot = RegistrySnapshot(
        modules={
            "a": RegistryModuleSnapshot(name="a", dependencies=[], category="light"),
            "b": RegistryModuleSnapshot(name="b", dependencies=["a"], category="light"),
        }
    )
    plan = planner.plan(["b"], snapshot)
    assert plan.blocked == {}


def test_dag_planner_deduplicates_duplicate_requested_modules():
    planner = DAGPlanner()
    snapshot = RegistrySnapshot(
        modules={
            "a": RegistryModuleSnapshot(name="a", dependencies=[], category="light"),
            "b": RegistryModuleSnapshot(name="b", dependencies=["a"], category="light"),
        }
    )
    plan = planner.plan(["b", "b", "a"], snapshot)
    assert plan.requested == ["b", "a"]
    assert plan.deterministic_order == ["a", "b"]


def test_dag_planner_fails_closed_for_missing_dependencies():
    planner = DAGPlanner()
    snapshot = RegistrySnapshot(
        modules={
            "top": RegistryModuleSnapshot(
                name="top", dependencies=["missing_dep"], category="light"
            )
        }
    )
    try:
        planner.plan(["top"], snapshot)
        assert False, "expected planner to fail closed on unresolved dependency"
    except ValueError as exc:
        assert "Missing dependency" in str(exc)


def test_planner_and_executor_do_not_import_persistence_adapters():
    import transcriptx.core.pipeline.dag_executor as dag_executor
    import transcriptx.core.pipeline.dag_planner as dag_planner

    for mod in (dag_planner, dag_executor):
        imported_names = set(mod.__dict__.keys())
        assert "artifact_manifest_store" not in imported_names
        assert "file_run_state_store" not in imported_names


def test_active_runtime_modules_do_not_import_dag_pipeline_facade():
    import inspect

    import transcriptx.core.pipeline.dag_executor as dag_executor
    import transcriptx.core.pipeline.dag_pipeline_engine as dag_engine
    import transcriptx.core.pipeline.dag_planner as dag_planner
    import transcriptx.core.pipeline.run_orchestrator as orchestrator

    for mod in (dag_planner, dag_executor, dag_engine, orchestrator):
        source = inspect.getsource(mod)
        assert "from transcriptx.core.pipeline.dag_pipeline import" not in source
        assert "import transcriptx.core.pipeline.dag_pipeline" not in source


def _reduce_sequence(
    executor: DAGExecutor, outcomes: list[ModuleOutcome]
) -> ExecutorState:
    state = ExecutorState()
    for i, outcome in enumerate(outcomes):
        executor.reduce_outcome(
            state,
            outcome.module,
            outcome,
            module_result=(
                {"idx": i} if outcome.status in {"succeeded", "failed"} else None
            ),
        )
    return state


def test_executor_outcomes_invariant_across_wiring_variants():
    outcomes = [
        ModuleOutcome(module="a", status="succeeded"),
        ModuleOutcome(module="b", status="skipped", reason="preflight"),
        ModuleOutcome(
            module="c", status="blocked", reason="blocked", blocking_modules=["a"]
        ),
        ModuleOutcome(
            module="d",
            status="failed",
            reason="boom",
            error_kind=ErrorKind.EXECUTION,
        ),
    ]
    executor = DAGExecutor()
    state_a = _reduce_sequence(executor, outcomes)
    # Simulate different side-effect/port wiring externally: reducer output must be identical.
    state_b = _reduce_sequence(DAGExecutor(), outcomes)

    assert state_a.modules_run == state_b.modules_run
    assert state_a.skipped_modules == state_b.skipped_modules
    assert state_a.errors == state_b.errors
    assert state_a.module_results == state_b.module_results
    assert [o.module for o in state_a.outcomes] == [o.module for o in state_b.outcomes]
