"""Run-performance schema constants and Pydantic models."""

from __future__ import annotations

import math
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

RUN_PERFORMANCE_SCHEMA_VERSION = 1
TIMING_SCOPE_VERSION = 1

MAX_SIDECAR_BYTES = 512 * 1024
MAX_STRING_LEN = 128
MAX_LLM_IDENTITIES = 16
MAX_LLM_BY_MODULE = 64


class ExecutionStatus(str, Enum):
    succeeded = "succeeded"
    partial = "partial"
    failed = "failed"
    aborted = "aborted"
    cancelled = "cancelled"


class FinalStatus(str, Enum):
    succeeded = "succeeded"
    partial = "partial"
    failed = "failed"
    aborted = "aborted"
    cancelled = "cancelled"
    persistence_degraded = "persistence_degraded"


class CacheProvenance(str, Enum):
    unwired = "unwired"
    none_recorded = "none_recorded"
    partial_hits = "partial_hits"
    all_executed_cached = "all_executed_cached"


def _finite_nonneg(name: str, value: float) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{name} must be a number")
    f = float(value)
    if not math.isfinite(f) or f < 0:
        raise ValueError(f"{name} must be finite and >= 0")
    return f


class LlmByModule(BaseModel):
    model_config = {"extra": "forbid"}

    module_id: str = Field(..., max_length=MAX_STRING_LEN)
    call_count: int = Field(..., ge=0)
    success_count: int = Field(..., ge=0)
    failure_count: int = Field(..., ge=0)
    retry_count: int = Field(..., ge=0)
    logical_wall_ms: float
    attempt_exec_ms: float = 0.0
    provider_total_duration_ns: Optional[int] = Field(default=None, ge=0)
    eval_count: Optional[int] = Field(default=None, ge=0)

    @field_validator("logical_wall_ms", "attempt_exec_ms")
    @classmethod
    def _ms_ok(cls, v: float, info: Any) -> float:
        return _finite_nonneg(info.field_name, v)


class LlmAggregate(BaseModel):
    model_config = {"extra": "forbid"}

    call_count: int = Field(..., ge=0)
    success_count: int = Field(..., ge=0)
    failure_count: int = Field(..., ge=0)
    retry_count: int = Field(..., ge=0)
    logical_wall_ms: float
    attempt_exec_ms: float = 0.0
    wait_ms: float = 0.0
    provider_total_duration_ns: Optional[int] = Field(default=None, ge=0)
    provider_load_duration_ns: Optional[int] = Field(default=None, ge=0)
    prompt_eval_count: Optional[int] = Field(default=None, ge=0)
    prompt_eval_duration_ns: Optional[int] = Field(default=None, ge=0)
    eval_count: Optional[int] = Field(default=None, ge=0)
    eval_duration_ns: Optional[int] = Field(default=None, ge=0)
    tokens_per_second: Optional[float] = None
    models: List[str] = Field(default_factory=list, max_length=MAX_LLM_IDENTITIES)
    efforts: List[str] = Field(default_factory=list, max_length=MAX_LLM_IDENTITIES)
    by_module: List[LlmByModule] = Field(
        default_factory=list, max_length=MAX_LLM_BY_MODULE
    )

    @field_validator("logical_wall_ms", "attempt_exec_ms", "wait_ms")
    @classmethod
    def _ms_ok(cls, v: float, info: Any) -> float:
        return _finite_nonneg(info.field_name, v)

    @field_validator("tokens_per_second")
    @classmethod
    def _tps_ok(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return None
        return _finite_nonneg("tokens_per_second", v)

    @model_validator(mode="after")
    def _counts_consistent(self) -> "LlmAggregate":
        if self.success_count + self.failure_count > self.call_count:
            raise ValueError("success_count + failure_count cannot exceed call_count")
        return self


class RuntimeFingerprint(BaseModel):
    model_config = {"extra": "forbid"}

    os_family: Optional[str] = Field(default=None, max_length=MAX_STRING_LEN)
    arch: Optional[str] = Field(default=None, max_length=MAX_STRING_LEN)
    python_version: Optional[str] = Field(default=None, max_length=MAX_STRING_LEN)
    cpu_class: Optional[str] = Field(default=None, max_length=MAX_STRING_LEN)
    memory_band: Optional[str] = Field(default=None, max_length=MAX_STRING_LEN)
    acceleration: Optional[Literal["cpu", "cuda", "mps", "other"]] = None


class WorkloadSnapshot(BaseModel):
    model_config = {"extra": "forbid"}

    transcript_duration_s: Optional[float] = None
    word_count: Optional[int] = Field(default=None, ge=0)
    segment_count: Optional[int] = Field(default=None, ge=0)
    speaker_count: Optional[int] = Field(default=None, ge=0)

    @field_validator("transcript_duration_s")
    @classmethod
    def _dur_ok(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return None
        return _finite_nonneg("transcript_duration_s", v)


class AnalysisContextSnapshot(BaseModel):
    model_config = {"extra": "forbid"}

    mode: Optional[str] = Field(default=None, max_length=MAX_STRING_LEN)
    profile: Optional[str] = Field(default=None, max_length=MAX_STRING_LEN)
    config_hash: Optional[str] = Field(default=None, max_length=MAX_STRING_LEN)
    app_version: Optional[str] = Field(default=None, max_length=MAX_STRING_LEN)
    requested_module_count: Optional[int] = Field(default=None, ge=0)


class GroupPerformanceMeta(BaseModel):
    model_config = {"extra": "forbid"}

    member_count: int = Field(..., ge=0)
    members_completed: Optional[int] = Field(default=None, ge=0)
    members_failed: Optional[int] = Field(default=None, ge=0)
    partial: bool = False


class RunPerformanceV1(BaseModel):
    """Non-authoritative run-level telemetry + stable interpretative context."""

    model_config = {"extra": "forbid"}

    schema_version: Literal[1] = 1
    timing_scope_version: Literal[1] = 1
    run_id: str = Field(..., min_length=1, max_length=MAX_STRING_LEN)
    target_type: Literal["transcript", "group"]
    wall_clock_duration_ms: float
    execution_status: ExecutionStatus
    final_status: FinalStatus
    termination_reason_code: Optional[str] = Field(
        default=None, max_length=MAX_STRING_LEN
    )
    cache_provenance: CacheProvenance = CacheProvenance.unwired
    analysis: Optional[AnalysisContextSnapshot] = None
    workload: Optional[WorkloadSnapshot] = None
    runtime_fingerprint: Optional[RuntimeFingerprint] = None
    llm: Optional[LlmAggregate] = None
    group: Optional[GroupPerformanceMeta] = None

    @field_validator("wall_clock_duration_ms")
    @classmethod
    def _wall_ok(cls, v: float) -> float:
        return _finite_nonneg("wall_clock_duration_ms", v)

    @model_validator(mode="after")
    def _group_meta_matches_target_type(self) -> "RunPerformanceV1":
        if self.target_type == "group" and self.group is None:
            raise ValueError("group metadata required when target_type is group")
        if self.target_type == "transcript" and self.group is not None:
            raise ValueError("group metadata forbidden when target_type is transcript")
        return self

    def to_json_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)
