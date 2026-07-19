"""Provider-neutral LLM metrics sink (no pipeline/web imports)."""

from __future__ import annotations

from typing import Optional, Protocol


class LlmMetricsSink(Protocol):
    def record_generate(
        self,
        *,
        success: bool,
        retry_count: int,
        logical_wall_ms: float,
        attempt_exec_ms: float,
        wait_ms: float = 0.0,
        model: Optional[str] = None,
        effort: Optional[str] = None,
        provider_total_duration_ns: Optional[int] = None,
        provider_load_duration_ns: Optional[int] = None,
        prompt_eval_count: Optional[int] = None,
        prompt_eval_duration_ns: Optional[int] = None,
        eval_count: Optional[int] = None,
        eval_duration_ns: Optional[int] = None,
    ) -> None: ...


class NullLlmMetricsSink:
    def record_generate(self, **kwargs: object) -> None:
        return None


_NULL = NullLlmMetricsSink()


def get_noop_llm_metrics_sink() -> LlmMetricsSink:
    return _NULL


class RecorderBackedLlmMetricsSink:
    """Forwards into the active RunPerformanceRecorder when bound."""

    def record_generate(
        self,
        *,
        success: bool,
        retry_count: int,
        logical_wall_ms: float,
        attempt_exec_ms: float,
        wait_ms: float = 0.0,
        model: Optional[str] = None,
        effort: Optional[str] = None,
        provider_total_duration_ns: Optional[int] = None,
        provider_load_duration_ns: Optional[int] = None,
        prompt_eval_count: Optional[int] = None,
        prompt_eval_duration_ns: Optional[int] = None,
        eval_count: Optional[int] = None,
        eval_duration_ns: Optional[int] = None,
    ) -> None:
        # Lazy import keeps llm package free of hard pipeline deps at import time.
        from transcriptx.core.observability.run_performance.recorder import (
            get_active_recorder,
        )

        rec = get_active_recorder()
        if rec is None:
            return
        rec.record_llm_call(
            success=success,
            retry_count=retry_count,
            logical_wall_ms=logical_wall_ms,
            attempt_exec_ms=attempt_exec_ms,
            wait_ms=wait_ms,
            model=model,
            effort=effort,
            provider_total_duration_ns=provider_total_duration_ns,
            provider_load_duration_ns=provider_load_duration_ns,
            prompt_eval_count=prompt_eval_count,
            prompt_eval_duration_ns=prompt_eval_duration_ns,
            eval_count=eval_count,
            eval_duration_ns=eval_duration_ns,
        )
