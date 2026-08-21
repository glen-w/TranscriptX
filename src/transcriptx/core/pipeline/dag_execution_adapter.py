"""Execute a single DAG module and apply side effects."""

from __future__ import annotations

import concurrent.futures
import contextvars
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
from transcriptx.core.pipeline.run_control import (
    SKIP_REASON_CANCELLED,
    SKIP_REASON_USER,
    get_bound_run_control,
    pipeline_consume_skip,
    pipeline_is_cancelled,
)

_ISOLATION_POLL_S = 0.25


def _elapsed_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000.0


def _resolve_running_llm_model(module_name: str) -> Optional[str]:
    """Best-effort Ollama tag for the user-facing module start banner.

    Returns ``None`` for non-LLM modules, empty custom-QA runs (no live call),
    or when resolution fails — the run itself still proceeds.
    """
    from transcriptx.core.analysis.llm_support.model_selection import (
        LLM_MODEL_CONSUMER_ID_SET,
        resolve_module_llm_model,
    )

    if module_name not in LLM_MODEL_CONSUMER_ID_SET:
        return None
    try:
        from transcriptx.core.analysis.llm_custom_qa.gating import (
            consumer_requires_live_llm,
        )

        if not consumer_requires_live_llm(module_name):
            return None
    except Exception:
        pass
    try:
        from transcriptx.core.utils.config import get_config

        resolved = resolve_module_llm_model(get_config().llm, module_name)
        model = str(resolved.model or "").strip()
        return model or None
    except Exception:
        return None


def _resolve_module_timeout_seconds(module_name: str, node: Any) -> int:
    """Wall-clock budget for a module. ``<= 0`` means no limit."""
    raw = getattr(node, "timeout_seconds", 600)
    try:
        timeout = int(raw)
    except (TypeError, ValueError):
        timeout = 600

    # Config / env can stretch or shrink the registry budget for BERTopic.
    if module_name == "bertopic":
        try:
            from transcriptx.core.utils.config import get_config

            cfg = getattr(get_config().analysis, "bertopic", None)
            cfg_timeout = getattr(cfg, "timeout_seconds", None)
            if cfg_timeout is not None:
                timeout = int(float(cfg_timeout))
        except Exception:
            pass
    return timeout


def _timeout_module_outcome(
    *,
    pipeline: Any,
    module_name: str,
    module_start: float,
    module_started_at: str,
    module_run: Any,
    timeout_seconds: int,
    build_module_result: Any,
    now_iso: Any,
) -> ModuleExecOutcome:
    duration_ms = _elapsed_ms(module_start)
    message = (
        f"Module '{module_name}' timed out after {timeout_seconds}s; "
        "abandoning this module and continuing the pipeline"
    )
    pipeline.logger.error(message)
    err_module_result = build_module_result(
        module_name=module_name,
        status="error",
        started_at=module_started_at,
        finished_at=now_iso(),
        artifacts=[],
        metrics={
            "duration_seconds": duration_ms / 1000.0,
            "timeout_seconds": float(timeout_seconds),
        },
        payload_type="analysis_results",
        payload={},
        error={
            "error_type": "TimeoutError",
            "error_message": message,
            "error_code": "module_timeout",
            "traceback_text": "",
        },
    )
    return ModuleExecOutcome(
        status="failed",
        module_result=err_module_result,
        error=message,
        duration_ms=duration_ms,
        module_run=module_run,
        module_started_at=module_started_at,
    )


def _await_isolated_module(
    future: concurrent.futures.Future[ModuleExecOutcome],
    *,
    pipeline: Any,
    module_name: str,
    module_start: float,
    module_started_at: str,
    module_run: Any,
    timeout_seconds: int,
    build_module_result: Any,
    now_iso: Any,
) -> ModuleExecOutcome:
    """Wait for an isolated module worker; honour timeout, skip, and cancel."""
    deadline = None if timeout_seconds <= 0 else module_start + float(timeout_seconds)
    while True:
        now = time.perf_counter()
        if deadline is not None and now >= deadline:
            return _timeout_module_outcome(
                pipeline=pipeline,
                module_name=module_name,
                module_start=module_start,
                module_started_at=module_started_at,
                module_run=module_run,
                timeout_seconds=timeout_seconds,
                build_module_result=build_module_result,
                now_iso=now_iso,
            )
        wait_s = _ISOLATION_POLL_S
        if deadline is not None:
            wait_s = min(_ISOLATION_POLL_S, max(deadline - now, 0.01))
        try:
            return future.result(timeout=wait_s)
        except concurrent.futures.TimeoutError:
            if pipeline_is_cancelled():
                return ModuleExecOutcome(
                    status="skipped",
                    skip_reason=SKIP_REASON_CANCELLED,
                    duration_ms=_elapsed_ms(module_start),
                    module_run=module_run,
                    module_started_at=module_started_at,
                )
            if pipeline_consume_skip():
                pipeline.logger.info(
                    "Skipping module '%s' at user request", module_name
                )
                return ModuleExecOutcome(
                    status="skipped",
                    skip_reason=SKIP_REASON_USER,
                    duration_ms=_elapsed_ms(module_start),
                    module_run=module_run,
                    module_started_at=module_started_at,
                )


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
            duration_s = (
                None
                if outcome.duration_ms is None
                else float(outcome.duration_ms) / 1000.0
            )
            run_report.record_module(
                module_name=module_name,
                status=ModuleResult.RUN,
                duration_seconds=duration_s if duration_s is not None else 0.0,
                reason="cache_hit",
            )
        return
    if outcome.status == "skipped" or outcome.status == "blocked":
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
        dur = outcome.duration_ms
        if dur is not None:
            pipeline.logger.info(f"{module_name} completed in {dur / 1000.0:.2f}s")
        if run_report:
            run_report.record_module(
                module_name=module_name,
                status=ModuleResult.RUN,
                duration_seconds=(dur / 1000.0) if dur is not None else None,
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
            duration_seconds=(
                (outcome.duration_ms / 1000.0)
                if outcome.duration_ms is not None
                else None
            ),
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
            flags = {}
            try:
                raw_flags = context.get_runtime_flags() if context is not None else None
                if isinstance(raw_flags, dict):
                    flags = raw_flags
            except Exception:
                flags = {}
            allow_unnamed = bool(flags.get("allow_unnamed_speakers"))
            turn_taking_count = (
                gating_turn_taking_speaker_count(context) if allow_unnamed else None
            )
            reason_text = speaker_gate_skip_reason(
                module_info,
                named_speaker_count=named_speaker_count,
                turn_taking_speaker_count=turn_taking_count,
                allow_unnamed_speakers=allow_unnamed,
            )
            if reason_text:
                return ModuleExecOutcome(status="skipped", skip_reason=reason_text)
    except Exception:
        pass

    module_run = None
    llm_model = _resolve_running_llm_model(module_name)
    if llm_model:
        pipeline.logger.info(f"Running {module_name} analysis (model={llm_model})")
        notify_user(
            f"🔍 Running {node.description} (model: {llm_model})...",
            technical=False,
            section=module_name,
        )
    else:
        pipeline.logger.info(f"Running {module_name} analysis")
        notify_user(
            f"🔍 Running {node.description}...", technical=False, section=module_name
        )
    log_analysis_start(module_name, transcript_path)
    module_start = time.perf_counter()
    module_started_at = now_iso()
    from transcriptx.core.observability.run_performance.recorder import (
        get_active_recorder,
    )

    recorder = get_active_recorder()
    module_ctx = recorder.module_scope(module_name) if recorder is not None else None
    if module_ctx is not None:
        module_ctx.__enter__()
    heartbeat_stop_event = threading.Event()
    heartbeat_thread = threading.Thread(
        target=pipeline._module_progress_heartbeat,
        args=(module_name, module_start, heartbeat_stop_event),
        daemon=True,
    )
    heartbeat_thread.start()

    def _run_module_body() -> ModuleExecOutcome:
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
                        return ModuleExecOutcome(
                            status="failed",
                            module_result=module_result,
                            error=str(err.get("error_message", "Unknown error")),
                            duration_ms=_elapsed_ms(module_start),
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
                        return ModuleExecOutcome(
                            status="failed",
                            module_result=module_result,
                            error=str(err.get("error_message", "Unknown error")),
                            duration_ms=_elapsed_ms(module_start),
                            module_run=module_run,
                            module_started_at=module_started_at,
                        )
                    raise RuntimeError(err if err else "Unknown error")
            else:
                node.function(transcript_path)
            duration_ms = _elapsed_ms(module_start)
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
            duration_ms = _elapsed_ms(module_start)
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
            duration_ms = _elapsed_ms(module_start)
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

    try:
        timeout_seconds = _resolve_module_timeout_seconds(module_name, node)
        control = get_bound_run_control()
        if timeout_seconds <= 0 and control is None:
            return _run_module_body()

        # wait=False on shutdown so a hung native fit does not block later modules.
        # Copy contextvars so a bound RunWriterLease reaches the worker thread.
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            ctx = contextvars.copy_context()
            future = executor.submit(ctx.run, _run_module_body)
            return _await_isolated_module(
                future,
                pipeline=pipeline,
                module_name=module_name,
                module_start=module_start,
                module_started_at=module_started_at,
                module_run=module_run,
                timeout_seconds=timeout_seconds,
                build_module_result=build_module_result,
                now_iso=now_iso,
            )
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
    finally:
        heartbeat_stop_event.set()
        heartbeat_thread.join(timeout=0.2)
        if module_ctx is not None:
            module_ctx.__exit__(None, None, None)
