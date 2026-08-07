"""Runtime entry that executes a planned DAG pipeline."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from transcriptx.core.pipeline.dag_pipeline_finalize import finalize_execution_results
from transcriptx.core.pipeline.dag_pipeline_run import (
    resolve_output_dir_for_run,
)
from transcriptx.core.pipeline.module_registry import list_finalize_phase_modules
from transcriptx.core.pipeline.run_options import SpeakerRunOptions


def execute_pipeline_runtime(
    pipeline: Any,
    *,
    transcript_path: str,
    selected_modules: List[str],
    speaker_options: "SpeakerRunOptions | None" = None,
    output_dir: Optional[str] = None,
    transcript_key: Optional[str] = None,
    run_id: Optional[str] = None,
    run_report: Optional[Any] = None,
    requirements_resolver: Optional[Any] = None,
    event_collector: Optional[List[Dict[str, Any]]] = None,
    on_event: Optional[Any] = None,
    context: Optional[Any] = None,
    named_speaker_count: Optional[int] = None,
    execution_plan: Optional[Any] = None,
) -> Dict[str, Any]:
    speaker_options = speaker_options or SpeakerRunOptions()
    pipeline.logger.info(f"Starting DAG pipeline for {transcript_path}")

    def emit(event_dict: Dict[str, Any]) -> None:
        pipeline._pipeline_emit(event_collector, on_event, event_dict)

    output_dir = resolve_output_dir_for_run(transcript_path, output_dir)
    results = pipeline._new_pipeline_results(transcript_path, selected_modules)

    if context is None:
        raise pipeline.__class__.PipelineSetupError(  # type: ignore[attr-defined]
            "PipelineContext must be injected by orchestrator; context required."
        )

    try:
        if not pipeline._validate_pipeline_io(transcript_path, output_dir, results):
            finalize_execution_results(
                results=results,
                execution_order=[],
                aborted=False,
                setup_failed=True,
                total_modules=0,
                ev_completed=0,
                ev_skipped=0,
                ev_failed=1,
                emit=emit,
                setup_error="; ".join(results.get("errors", [])),
            )
            return results

        if not pipeline._finalized:
            try:
                pipeline.finalize()
            except ValueError as e:
                pipeline.logger.error(f"Registry finalization failed: {e}")

        preflight = pipeline.preflight_check(selected_modules)
        if preflight["warnings"]:
            for warning in preflight["warnings"]:
                pipeline.logger.warning(f"Preflight warning: {warning}")
        if not preflight["all_importable"]:
            missing = ", ".join(preflight["missing_dependencies"])
            pipeline.logger.error(
                f"Preflight check failed: modules cannot be imported: {missing}"
            )

        setup_error: Optional[str] = None
        try:
            plan = execution_plan or pipeline.get_execution_plan(selected_modules)
        except Exception as e:
            pipeline.logger.error(str(e))
            results["errors"].append(str(e))
            results["status"] = "failed"
            setup_error = str(e)
            plan = None
        if plan is None:
            finalize_execution_results(
                results=results,
                execution_order=[],
                aborted=False,
                setup_failed=True,
                total_modules=0,
                ev_completed=0,
                ev_skipped=0,
                ev_failed=1,
                emit=emit,
                setup_error=setup_error,
            )
            return results

        execution_order = list(plan.deterministic_order)
        pipeline.logger.info(f"Execution order: {', '.join(execution_order)}")
        results["execution_order"] = execution_order

        pending_finalize = list_finalize_phase_modules(selected_modules)
        progress_total = len(execution_order) + len(pending_finalize)

        named_speaker_count_ref = [named_speaker_count]
        for blocked_outcome in pipeline._executor.blocked_from_plan(plan):
            pipeline._executor.reduce_outcome(
                pipeline._new_executor_state(results),
                blocked_outcome.module,
                blocked_outcome,
            )

        (
            aborted,
            total_modules,
            ev_completed,
            ev_skipped,
            ev_failed,
            abort_error,
        ) = pipeline._run_sequential_execution_phase(
            execution_order=execution_order,
            results=results,
            context=context,
            transcript_path=transcript_path,
            run_report=run_report,
            requirements_resolver=requirements_resolver,
            named_speaker_count_ref=named_speaker_count_ref,
            emit=emit,
            progress_total=progress_total,
        )

        finalize_execution_results(
            results=results,
            execution_order=execution_order,
            aborted=aborted,
            setup_failed=False,
            total_modules=total_modules,
            ev_completed=ev_completed,
            ev_skipped=ev_skipped,
            ev_failed=ev_failed,
            emit=emit,
            abort_error=abort_error,
            setup_error=None,
            pending_finalize_modules=pending_finalize,
        )
        pipeline.logger.info(
            f"Pipeline completed. Ran {len(results['modules_run'])} modules with {len(results['errors'])} errors"
        )
        return results
    finally:
        pass
