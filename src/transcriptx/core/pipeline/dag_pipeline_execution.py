"""Sequential DAG module execution loop (extracted from DAGPipeline)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from transcriptx.core.pipeline.dag_pipeline_progress import (
    module_completed_event,
    module_failed_event,
    module_skipped_event,
    module_started_event,
    run_started_event,
)
from transcriptx.core.pipeline.dag_pipeline_types import ModuleExecOutcome
from transcriptx.core.utils.speaker_extraction import named_speaker_count_for_path

if TYPE_CHECKING:
    from transcriptx.core.pipeline.dag_pipeline import DAGPipeline


def run_sequential_execution_phase(
    pipeline: DAGPipeline,
    *,
    execution_order: List[str],
    results: Dict[str, Any],
    context: Any,
    transcript_path: str,
    run_report: Optional[Any],
    requirements_resolver: Optional[Any],
    named_speaker_count_ref: List[Optional[int]],
    emit: Callable[[Dict[str, Any]], None],
    progress_total: Optional[int] = None,
) -> Tuple[bool, int, int, int, int, str | None]:
    """Execute modules in order. Mutates ``results`` and ``named_speaker_count_ref[0]``.

    ``progress_total`` may exceed ``len(execution_order)`` when finalize-phase
    modules (e.g. chart_descriptions) are counted toward the UI total but run
    after the DAG.
    """
    total_modules = (
        int(progress_total)
        if progress_total is not None
        else len(execution_order)
    )
    ev_completed = 0
    ev_skipped = 0
    ev_failed = 0

    emit(run_started_event(total_modules=total_modules))

    aborted = False
    abort_error: str | None = None
    for idx_0, module_name in enumerate(execution_order):
        index = idx_0 + 1

        if module_name not in pipeline.nodes:
            pipeline.logger.warning(f"Unknown module: {module_name}")
            pipeline._reduce_module_outcome(
                module_name=module_name,
                outcome=ModuleExecOutcome(
                    status="blocked",
                    skip_reason="unknown_module",
                ),
                results=results,
            )
            continue

        node = pipeline.nodes[module_name]

        missing_deps = pipeline._check_missing_dependencies(
            node, results["modules_run"]
        )
        if missing_deps:
            ev_skipped += 1
            emit(
                module_skipped_event(
                    module_name=module_name,
                    index=index,
                    total_modules=total_modules,
                    ev_completed=ev_completed,
                    ev_skipped=ev_skipped,
                    ev_failed=ev_failed,
                    message="missing_dependencies",
                )
            )
            dep_chain = []
            for dep in missing_deps:
                if dep in pipeline.nodes:
                    dep_node = pipeline.nodes[dep]
                    missing_dep_deps = pipeline._check_missing_dependencies(
                        dep_node, results["modules_run"]
                    )
                    if missing_dep_deps:
                        dep_chain.append(f"{dep} (which requires {missing_dep_deps})")
                    else:
                        dep_chain.append(dep)
                else:
                    dep_chain.append(dep)

            error_msg = f"{module_name}: Missing dependencies {missing_deps}"
            if dep_chain != missing_deps:
                error_msg += f" ({', '.join(dep_chain)})"

            pipeline.logger.warning(
                f"Module '{module_name}' missing dependencies: {missing_deps}"
            )
            pipeline._reduce_module_outcome(
                module_name=module_name,
                outcome=ModuleExecOutcome(
                    status="blocked",
                    skip_reason=error_msg,
                ),
                results=results,
            )
            continue

        if named_speaker_count_ref[0] is None and context is not None:
            try:
                named_speaker_count_ref[0] = named_speaker_count_for_path(
                    transcript_path
                )
            except Exception:
                named_speaker_count_ref[0] = None

        emit(
            module_started_event(
                module_name=module_name,
                index=index,
                total_modules=total_modules,
                ev_completed=ev_completed,
                ev_skipped=ev_skipped,
                ev_failed=ev_failed,
            )
        )
        outcome = pipeline._execute_single_module(
            module_name=module_name,
            node=node,
            transcript_path=transcript_path,
            context=context,
            run_report=run_report,
            requirements_resolver=requirements_resolver,
            named_speaker_count=named_speaker_count_ref[0],
        )
        if outcome.status == "success":
            ev_completed += 1
            emit(
                module_completed_event(
                    module_name=module_name,
                    index=index,
                    total_modules=total_modules,
                    ev_completed=ev_completed,
                    ev_skipped=ev_skipped,
                    ev_failed=ev_failed,
                    duration_ms=outcome.duration_ms,
                )
            )
        elif outcome.status == "skipped":
            ev_skipped += 1
            emit(
                module_skipped_event(
                    module_name=module_name,
                    index=index,
                    total_modules=total_modules,
                    ev_completed=ev_completed,
                    ev_skipped=ev_skipped,
                    ev_failed=ev_failed,
                    message=outcome.skip_reason or "unknown",
                )
            )
        else:
            ev_failed += 1
            error_code = None
            module_result = getattr(outcome, "module_result", None)
            if module_result:
                err_payload = module_result.get("error") or {}
                if isinstance(err_payload, dict):
                    error_code = err_payload.get("error_code")
            emit(
                module_failed_event(
                    module_name=module_name,
                    index=index,
                    total_modules=total_modules,
                    ev_completed=ev_completed,
                    ev_skipped=ev_skipped,
                    ev_failed=ev_failed,
                    error=outcome.error,
                    error_code=error_code,
                )
            )

        pipeline._reduce_module_outcome(
            module_name=module_name,
            outcome=outcome,
            results=results,
        )
        pipeline._apply_module_side_effects(
            module_name=module_name,
            node=node,
            outcome=outcome,
            transcript_path=transcript_path,
            run_report=run_report,
        )
        if outcome.status == "failed" and pipeline._should_abort_pipeline(
            outcome, results
        ):
            aborted = True
            abort_error = outcome.error
            break

    return aborted, total_modules, ev_completed, ev_skipped, ev_failed, abort_error
