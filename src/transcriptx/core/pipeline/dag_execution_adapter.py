from __future__ import annotations

import threading
import time
from typing import Any, Optional

from transcriptx.core.utils.logger import (
    log_analysis_complete,
    log_analysis_error,
    log_analysis_start,
)
from transcriptx.core.utils.notifications import notify_user
from transcriptx.core.pipeline.dag_pipeline_types import ModuleExecOutcome


def apply_module_side_effects(
    pipeline: Any,
    *,
    module_name: str,
    node: Any,
    outcome: Any,
    transcript_path: str,
    run_report: Optional[Any],
) -> None:
    from transcriptx.core.utils.run_report import ModuleResult

    if outcome.used_cache:
        if run_report:
            run_report.record_module(
                module_name=module_name,
                status=ModuleResult.RUN,
                duration_seconds=0.0,
                reason="cache_hit",
            )
        return
    if outcome.status == "skipped":
        if run_report and outcome.skip_reason:
            run_report.record_module(
                module_name=module_name,
                status=ModuleResult.SKIP,
                reason=outcome.skip_reason,
            )
        return
    if outcome.status == "success":
        notify_user(
            f"✅ Completed {node.description}",
            technical=False,
            section=module_name,
        )
        log_analysis_complete(module_name, transcript_path)
        pipeline.logger.info(
            f"{module_name} completed in {outcome.duration_ms / 1000.0:.2f}s"
        )
        if run_report:
            run_report.record_module(
                module_name=module_name,
                status=ModuleResult.RUN,
                duration_seconds=outcome.duration_ms / 1000.0,
            )
        return
    notify_user(
        f"❌ Failed {node.description}: {outcome.error}",
        technical=True,
        section=module_name,
    )
    log_analysis_error(module_name, transcript_path, Exception(outcome.error or ""))
    if run_report:
        run_report.record_module(
            module_name=module_name,
            status=ModuleResult.FAIL,
            error=outcome.error,
        )


def execute_single_module(
    pipeline: Any,
    *,
    module_name: str,
    node: Any,
    transcript_path: str,
    context: Optional[Any],
    requirements_resolver: Optional[Any],
    named_speaker_count: Optional[int],
) -> Any:
    from transcriptx.core.errors.coded import CodedError
    from transcriptx.core.utils.module_result import (
        build_module_result,
        capture_exception,
        now_iso,
    )

    if requirements_resolver:
        should_skip, reasons = requirements_resolver.should_skip(node.requirements)
        if should_skip:
            return ModuleExecOutcome(status="skipped", skip_reason="; ".join(reasons))

    from transcriptx.core.pipeline.dag_pipeline_run import (
        evaluate_llm_gate,
        gating_turn_taking_speaker_count,
        speaker_gate_skip_reason,
    )
    from transcriptx.core.pipeline.module_registry import get_module_info

    gate_action, gate_skip_reason, gate_fail_message = evaluate_llm_gate(module_name)
    if gate_action == "skip":
        return ModuleExecOutcome(status="skipped", skip_reason=gate_skip_reason)
    if gate_action == "fail":
        from transcriptx.core.llm.errors import LLMConfigurationError

        config_exc = LLMConfigurationError(gate_fail_message or "LLM gate failed")
        err_module_result = build_module_result(
            module_name=module_name,
            status="error",
            started_at=now_iso(),
            finished_at=now_iso(),
            artifacts=[],
            metrics={"duration_seconds": 0.0},
            payload_type="analysis_results",
            payload={},
            error=capture_exception(config_exc),
        )
        return ModuleExecOutcome(
            status="failed",
            module_result=err_module_result,
            error=str(config_exc),
            duration_ms=0.0,
            module_run=None,
            module_started_at=now_iso(),
        )

    try:
        module_info = get_module_info(module_name)
        if module_info:
            turn_taking_count = (
                gating_turn_taking_speaker_count(context)
                if getattr(module_info, "gate_on_turn_taking_speakers", False)
                else None
            )
            reason_text = speaker_gate_skip_reason(
                module_info,
                named_speaker_count=named_speaker_count,
                turn_taking_speaker_count=turn_taking_count,
            )
            if reason_text:
                return ModuleExecOutcome(status="skipped", skip_reason=reason_text)
    except Exception:
        pass

    module_run = None
    pipeline.logger.info(f"Running {module_name} analysis")
    notify_user(
        f"🔍 Running {node.description}...", technical=False, section=module_name
    )
    log_analysis_start(module_name, transcript_path)
    module_start = time.time()
    module_started_at = now_iso()
    heartbeat_stop_event = threading.Event()
    heartbeat_thread = threading.Thread(
        target=pipeline._module_progress_heartbeat,
        args=(module_name, module_start, heartbeat_stop_event),
        daemon=True,
    )
    heartbeat_thread.start()
    module_result = None
    try:
        if context is None:
            raise RuntimeError("PipelineContext is required for module execution")
        execution_context = context
        if isinstance(node.function, type) and hasattr(
            node.function, "run_from_context"
        ):
            module_instance = node.function()
            module_result = module_instance.run_from_context(execution_context)
            if module_result.get("status") == "error":
                err = module_result.get("error", {})
                if isinstance(err, dict) and err.get("error_code"):
                    duration_ms = (time.time() - module_start) * 1000
                    return ModuleExecOutcome(
                        status="failed",
                        module_result=module_result,
                        error=str(err.get("error_message", "Unknown error")),
                        duration_ms=duration_ms,
                        module_run=module_run,
                        module_started_at=module_started_at,
                    )
                raise RuntimeError(err if err else "Unknown error")
        elif hasattr(type(node.function), "run_from_context") and not isinstance(
            node.function, type
        ):
            module_result = node.function.run_from_context(execution_context)
            if module_result.get("status") == "error":
                err = module_result.get("error", {})
                if isinstance(err, dict) and err.get("error_code"):
                    duration_ms = (time.time() - module_start) * 1000
                    return ModuleExecOutcome(
                        status="failed",
                        module_result=module_result,
                        error=str(err.get("error_message", "Unknown error")),
                        duration_ms=duration_ms,
                        module_run=module_run,
                        module_started_at=module_started_at,
                    )
                raise RuntimeError(err if err else "Unknown error")
        else:
            node.function(transcript_path)
        duration_ms = (time.time() - module_start) * 1000
        if module_result is None:
            module_result = build_module_result(
                module_name=module_name,
                status="success",
                started_at=module_started_at,
                finished_at=now_iso(),
                artifacts=[],
                metrics={"duration_seconds": duration_ms / 1000.0},
                payload_type="analysis_results",
                payload={},
            )
        return ModuleExecOutcome(
            status="success",
            module_result=module_result,
            duration_ms=duration_ms,
            module_run=module_run,
            module_started_at=module_started_at,
        )
    except CodedError as e:
        pipeline.logger.error(f"Error in {module_name} analysis: {str(e)}")
        duration_ms = (time.time() - module_start) * 1000
        err_module_result = build_module_result(
            module_name=module_name,
            status="error",
            started_at=module_started_at,
            finished_at=now_iso(),
            artifacts=[],
            metrics={"duration_seconds": duration_ms / 1000.0},
            payload_type="analysis_results",
            payload={},
            error=capture_exception(e),
        )
        return ModuleExecOutcome(
            status="failed",
            module_result=err_module_result,
            error=str(e),
            duration_ms=duration_ms,
            module_run=module_run,
            module_started_at=module_started_at,
        )
    except Exception as e:
        pipeline.logger.error(f"Error in {module_name} analysis: {str(e)}")
        duration_ms = (time.time() - module_start) * 1000
        err_module_result = build_module_result(
            module_name=module_name,
            status="error",
            started_at=module_started_at,
            finished_at=now_iso(),
            artifacts=[],
            metrics={"duration_seconds": duration_ms / 1000.0},
            payload_type="analysis_results",
            payload={},
            error=capture_exception(e),
        )
        return ModuleExecOutcome(
            status="failed",
            module_result=err_module_result,
            error=str(e),
            duration_ms=duration_ms,
            module_run=module_run,
            module_started_at=module_started_at,
        )
    finally:
        heartbeat_stop_event.set()
        heartbeat_thread.join(timeout=0.2)
