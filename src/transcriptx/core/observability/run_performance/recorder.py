"""Run-scoped performance accumulator with exactly-once freeze semantics."""

from __future__ import annotations

import threading
import time
from contextvars import ContextVar, Token
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from transcriptx.core.observability.run_performance.schema import (
    AnalysisContextSnapshot,
    CacheProvenance,
    ExecutionStatus,
    FinalStatus,
    GroupPerformanceMeta,
    LlmAggregate,
    LlmByModule,
    MAX_LLM_BY_MODULE,
    MAX_LLM_IDENTITIES,
    MAX_STRING_LEN,
    RunPerformanceV1,
    RuntimeFingerprint,
    TIMING_SCOPE_VERSION,
    WorkloadSnapshot,
)

_active_recorder: ContextVar[Optional["RunPerformanceRecorder"]] = ContextVar(
    "tx_run_performance_recorder", default=None
)
_current_module_id: ContextVar[Optional[str]] = ContextVar(
    "tx_run_performance_module_id", default=None
)

# Non-user-visible placeholder until set_run_id assigns the authoritative ID.
PENDING_RUN_ID = "pending"


class RecorderState(str, Enum):
    created = "created"
    running = "running"
    stopped = "stopped"
    frozen = "frozen"
    persisted = "persisted"
    persist_failed = "persist_failed"


@dataclass
class _LlmCallBucket:
    call_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    retry_count: int = 0
    logical_wall_ms: float = 0.0
    attempt_exec_ms: float = 0.0
    wait_ms: float = 0.0
    provider_total_duration_ns: int = 0
    provider_load_duration_ns: int = 0
    prompt_eval_count: int = 0
    prompt_eval_duration_ns: int = 0
    eval_count: int = 0
    eval_duration_ns: int = 0
    has_provider_total: bool = False
    has_provider_load: bool = False
    has_prompt_eval_count: bool = False
    has_prompt_eval_duration: bool = False
    has_eval_count: bool = False
    has_eval_duration: bool = False


def get_active_recorder() -> Optional["RunPerformanceRecorder"]:
    return _active_recorder.get()


def get_current_module_id() -> Optional[str]:
    return _current_module_id.get()


class RunPerformanceRecorder:
    """Pure accumulator: wall clock + LLM aggregates. Persistence is external."""

    def __init__(self, *, run_id: str, target_type: str) -> None:
        self.run_id = run_id
        self.target_type = target_type
        self._lock = threading.RLock()
        self._state = RecorderState.created
        self._wall_start: Optional[float] = None
        self._wall_ms: Optional[float] = None
        self._llm_total = _LlmCallBucket()
        self._llm_by_module: Dict[str, _LlmCallBucket] = {}
        self._models: List[str] = []
        self._efforts: List[str] = []
        self._snapshot: Optional[RunPerformanceV1] = None
        self._bind_token: Optional[Token] = None

    def set_run_id(self, run_id: str) -> None:
        """Assign the authoritative run ID exactly once (from PENDING_RUN_ID)."""
        with self._lock:
            if self._state in {
                RecorderState.frozen,
                RecorderState.persisted,
                RecorderState.persist_failed,
            }:
                raise RuntimeError("cannot change run_id after freeze")
            authoritative = str(run_id or "").strip()
            if not authoritative or authoritative == PENDING_RUN_ID:
                raise ValueError("authoritative run_id required")
            if self.run_id != PENDING_RUN_ID:
                if self.run_id == authoritative:
                    return
                raise RuntimeError("run_id already assigned")
            self.run_id = authoritative[:MAX_STRING_LEN]

    @property
    def state(self) -> RecorderState:
        return self._state

    @property
    def wall_clock_duration_ms(self) -> Optional[float]:
        return self._wall_ms

    @property
    def wall_clock_duration_seconds(self) -> Optional[float]:
        if self._wall_ms is None:
            return None
        return self._wall_ms / 1000.0

    def bind(self) -> None:
        self._bind_token = _active_recorder.set(self)

    def unbind(self) -> None:
        if self._bind_token is not None:
            _active_recorder.reset(self._bind_token)
            self._bind_token = None

    def start_wall_clock(self) -> None:
        with self._lock:
            if self._state not in {RecorderState.created}:
                raise RuntimeError(f"cannot start wall clock in state {self._state}")
            self._wall_start = time.perf_counter()
            self._state = RecorderState.running

    def stop_wall_clock(self) -> float:
        """Stop after required persistence; returns wall ms. Idempotent once stopped."""
        with self._lock:
            if self._wall_ms is not None and self._state in {
                RecorderState.stopped,
                RecorderState.frozen,
                RecorderState.persisted,
                RecorderState.persist_failed,
            }:
                return self._wall_ms
            if self._state != RecorderState.running or self._wall_start is None:
                raise RuntimeError(f"cannot stop wall clock in state {self._state}")
            self._wall_ms = (time.perf_counter() - self._wall_start) * 1000.0
            self._state = RecorderState.stopped
            return self._wall_ms

    def module_scope(self, module_id: str) -> "_ModuleScope":
        return _ModuleScope(module_id)

    def record_llm_call(
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
        module_id: Optional[str] = None,
    ) -> None:
        mid = module_id if module_id is not None else get_current_module_id()
        key = mid or "unattributed"
        with self._lock:
            if self._state not in {
                RecorderState.running,
                RecorderState.stopped,
                RecorderState.created,
            }:
                return
            self._accumulate(
                self._llm_total,
                success=success,
                retry_count=retry_count,
                logical_wall_ms=logical_wall_ms,
                attempt_exec_ms=attempt_exec_ms,
                wait_ms=wait_ms,
                provider_total_duration_ns=provider_total_duration_ns,
                provider_load_duration_ns=provider_load_duration_ns,
                prompt_eval_count=prompt_eval_count,
                prompt_eval_duration_ns=prompt_eval_duration_ns,
                eval_count=eval_count,
                eval_duration_ns=eval_duration_ns,
            )
            bucket = self._llm_by_module.setdefault(key, _LlmCallBucket())
            self._accumulate(
                bucket,
                success=success,
                retry_count=retry_count,
                logical_wall_ms=logical_wall_ms,
                attempt_exec_ms=attempt_exec_ms,
                wait_ms=wait_ms,
                provider_total_duration_ns=provider_total_duration_ns,
                provider_load_duration_ns=provider_load_duration_ns,
                prompt_eval_count=prompt_eval_count,
                prompt_eval_duration_ns=prompt_eval_duration_ns,
                eval_count=eval_count,
                eval_duration_ns=eval_duration_ns,
            )
            self._note_identity(self._models, model)
            self._note_identity(self._efforts, effort)

    @staticmethod
    def _note_identity(store: List[str], value: Optional[str]) -> None:
        if not value:
            return
        clipped = str(value)[:MAX_STRING_LEN]
        if clipped not in store and len(store) < MAX_LLM_IDENTITIES:
            store.append(clipped)

    @staticmethod
    def _accumulate(
        bucket: _LlmCallBucket,
        *,
        success: bool,
        retry_count: int,
        logical_wall_ms: float,
        attempt_exec_ms: float,
        wait_ms: float,
        provider_total_duration_ns: Optional[int],
        provider_load_duration_ns: Optional[int],
        prompt_eval_count: Optional[int],
        prompt_eval_duration_ns: Optional[int],
        eval_count: Optional[int],
        eval_duration_ns: Optional[int],
    ) -> None:
        bucket.call_count += 1
        if success:
            bucket.success_count += 1
        else:
            bucket.failure_count += 1
        bucket.retry_count += max(0, int(retry_count))
        bucket.logical_wall_ms += max(0.0, float(logical_wall_ms))
        bucket.attempt_exec_ms += max(0.0, float(attempt_exec_ms))
        bucket.wait_ms += max(0.0, float(wait_ms))
        if provider_total_duration_ns is not None and provider_total_duration_ns >= 0:
            bucket.provider_total_duration_ns += int(provider_total_duration_ns)
            bucket.has_provider_total = True
        if provider_load_duration_ns is not None and provider_load_duration_ns >= 0:
            bucket.provider_load_duration_ns += int(provider_load_duration_ns)
            bucket.has_provider_load = True
        if prompt_eval_count is not None and prompt_eval_count >= 0:
            bucket.prompt_eval_count += int(prompt_eval_count)
            bucket.has_prompt_eval_count = True
        if prompt_eval_duration_ns is not None and prompt_eval_duration_ns >= 0:
            bucket.prompt_eval_duration_ns += int(prompt_eval_duration_ns)
            bucket.has_prompt_eval_duration = True
        if eval_count is not None and eval_count >= 0:
            bucket.eval_count += int(eval_count)
            bucket.has_eval_count = True
        if eval_duration_ns is not None and eval_duration_ns >= 0:
            bucket.eval_duration_ns += int(eval_duration_ns)
            bucket.has_eval_duration = True

    def freeze(
        self,
        *,
        execution_status: ExecutionStatus,
        final_status: FinalStatus,
        termination_reason_code: Optional[str] = None,
        cache_provenance: CacheProvenance = CacheProvenance.unwired,
        analysis: Optional[AnalysisContextSnapshot] = None,
        workload: Optional[WorkloadSnapshot] = None,
        runtime_fingerprint: Optional[RuntimeFingerprint] = None,
        group: Optional[GroupPerformanceMeta] = None,
    ) -> RunPerformanceV1:
        with self._lock:
            if self._state == RecorderState.frozen and self._snapshot is not None:
                return self._snapshot
            if self._state not in {RecorderState.stopped}:
                raise RuntimeError(f"cannot freeze in state {self._state}")
            if self._wall_ms is None:
                raise RuntimeError("wall clock not stopped")
            if not self.run_id or self.run_id == PENDING_RUN_ID:
                raise RuntimeError("cannot freeze without authoritative run_id")
            llm = self._build_llm_aggregate()
            snap = RunPerformanceV1(
                schema_version=1,
                timing_scope_version=TIMING_SCOPE_VERSION,
                run_id=self.run_id,
                target_type=self.target_type,  # type: ignore[arg-type]
                wall_clock_duration_ms=self._wall_ms,
                execution_status=execution_status,
                final_status=final_status,
                termination_reason_code=termination_reason_code,
                cache_provenance=cache_provenance,
                analysis=analysis,
                workload=workload,
                runtime_fingerprint=runtime_fingerprint,
                llm=llm,
                group=group,
            )
            self._snapshot = snap
            self._state = RecorderState.frozen
            return snap

    def mark_persisted(self, *, success: bool) -> None:
        with self._lock:
            if self._state not in {RecorderState.frozen}:
                raise RuntimeError(f"cannot mark persisted in state {self._state}")
            self._state = (
                RecorderState.persisted if success else RecorderState.persist_failed
            )

    def _build_llm_aggregate(self) -> Optional[LlmAggregate]:
        total = self._llm_total
        if total.call_count <= 0:
            return None
        tps = None
        if (
            total.has_eval_count
            and total.has_eval_duration
            and total.eval_count > 0
            and total.eval_duration_ns > 0
        ):
            tps = total.eval_count / (total.eval_duration_ns / 1e9)
        by_module: List[LlmByModule] = []
        for mid, bucket in sorted(self._llm_by_module.items()):
            if len(by_module) >= MAX_LLM_BY_MODULE:
                break
            by_module.append(
                LlmByModule(
                    module_id=mid[:MAX_STRING_LEN],
                    call_count=bucket.call_count,
                    success_count=bucket.success_count,
                    failure_count=bucket.failure_count,
                    retry_count=bucket.retry_count,
                    logical_wall_ms=bucket.logical_wall_ms,
                    attempt_exec_ms=bucket.attempt_exec_ms,
                    provider_total_duration_ns=(
                        bucket.provider_total_duration_ns
                        if bucket.has_provider_total
                        else None
                    ),
                    eval_count=bucket.eval_count if bucket.has_eval_count else None,
                )
            )
        return LlmAggregate(
            call_count=total.call_count,
            success_count=total.success_count,
            failure_count=total.failure_count,
            retry_count=total.retry_count,
            logical_wall_ms=total.logical_wall_ms,
            attempt_exec_ms=total.attempt_exec_ms,
            wait_ms=total.wait_ms,
            provider_total_duration_ns=(
                total.provider_total_duration_ns if total.has_provider_total else None
            ),
            provider_load_duration_ns=(
                total.provider_load_duration_ns if total.has_provider_load else None
            ),
            prompt_eval_count=(
                total.prompt_eval_count if total.has_prompt_eval_count else None
            ),
            prompt_eval_duration_ns=(
                total.prompt_eval_duration_ns
                if total.has_prompt_eval_duration
                else None
            ),
            eval_count=total.eval_count if total.has_eval_count else None,
            eval_duration_ns=(
                total.eval_duration_ns if total.has_eval_duration else None
            ),
            tokens_per_second=tps,
            models=list(self._models),
            efforts=list(self._efforts),
            by_module=by_module,
        )


class _ModuleScope:
    def __init__(self, module_id: str) -> None:
        self._module_id = module_id
        self._token: Optional[Token] = None

    def __enter__(self) -> "_ModuleScope":
        self._token = _current_module_id.set(self._module_id)
        return self

    def __exit__(self, *args: Any) -> None:
        if self._token is not None:
            _current_module_id.reset(self._token)
            self._token = None
