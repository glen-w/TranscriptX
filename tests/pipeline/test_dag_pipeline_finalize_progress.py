from __future__ import annotations

import transcriptx.core.pipeline.dag_pipeline_finalize as finalize_module
import transcriptx.core.pipeline.dag_pipeline_progress as progress_module


def test_finalize_execution_results_emits_completed_event_and_sets_duration() -> None:
    captured: list[dict] = []
    results = {"start_time": 10.0, "errors": [], "modules_run": []}
    out = finalize_module.finalize_execution_results(
        results=results,
        execution_order=["stats"],
        aborted=False,
        setup_failed=False,
        total_modules=1,
        ev_completed=1,
        ev_skipped=0,
        ev_failed=0,
        emit=lambda event: captured.append(event),
    )
    assert out["execution_order"] == ["stats"]
    assert out["duration"] >= 0
    assert captured[-1]["event"] == "run_completed"
    assert captured[-1]["pct"] == 100.0


def test_finalize_execution_results_prefers_setup_failed_over_aborted() -> None:
    captured: list[dict] = []
    finalize_module.finalize_execution_results(
        results={"start_time": 0.0, "errors": [], "modules_run": []},
        execution_order=[],
        aborted=True,
        setup_failed=True,
        total_modules=0,
        ev_completed=0,
        ev_skipped=0,
        ev_failed=1,
        emit=lambda event: captured.append(event),
        abort_error="abort",
        setup_error="setup",
    )
    assert captured[-1]["event"] == "run_failed"
    assert captured[-1]["message"] == "Pipeline failed during setup"
    assert captured[-1]["error"] == "setup"


def test_finalize_execution_results_swallow_emit_failure_and_keeps_result_state() -> (
    None
):
    results = {"start_time": 0.0, "errors": [], "modules_run": []}

    def _raise(_event: dict) -> None:
        raise RuntimeError("callback failed")

    out = finalize_module.finalize_execution_results(
        results=results,
        execution_order=["stats"],
        aborted=False,
        setup_failed=False,
        total_modules=1,
        ev_completed=1,
        ev_skipped=0,
        ev_failed=0,
        emit=_raise,
    )

    assert out is results
    assert out["execution_order"] == ["stats"]
    assert out["end_time"] >= out["start_time"]
    assert out["duration"] >= 0


def test_progress_helpers_build_consistent_progress_payloads() -> None:
    assert progress_module.progress_pct(1, 1, 0, 4) == 50.0
    started = progress_module.module_started_event(
        module_name="stats",
        index=1,
        total_modules=4,
        ev_completed=1,
        ev_skipped=0,
        ev_failed=1,
    )
    assert started["pct"] == 50.0
    skipped = progress_module.module_skipped_event(
        module_name="stats",
        index=2,
        total_modules=4,
        ev_completed=1,
        ev_skipped=1,
        ev_failed=1,
        message="missing_dependencies",
    )
    assert skipped["event"] == "module_skipped"
    assert skipped["message"] == "missing_dependencies"
    failed = progress_module.run_failed_event(
        total_modules=4,
        ev_completed=1,
        ev_skipped=1,
        ev_failed=1,
        error="boom",
        message="Pipeline aborted",
    )
    assert failed["event"] == "run_failed"
    assert failed["failed"] == 1
