"""Pydantic models for chart description artifacts and generation envelopes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from transcriptx.core.analysis.chart_descriptions.schemas import (
    DEFAULT_MAX_DESCRIPTION_CHARS,
    SCHEMA_ACTIVE,
    SCHEMA_ATTEMPT,
    SCHEMA_COMMIT,
    SCHEMA_DESCRIPTION,
    SCHEMA_INDEX,
    SCHEMA_OUTCOME,
    OverallStatus,
    UnitStatus,
)


class RepresentationModel(BaseModel):
    artifact_id: str
    rel_path: str
    kind: str
    format: str
    storage_root: str | None = None
    content_sha256: str | None = None


class ChartDescriptionArtifact(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    schema_id: Literal["transcriptx.chart_description.v1"] = SCHEMA_DESCRIPTION
    chart_key: str
    logical_chart_id: str
    viz_id: str
    module: str
    scope: str
    speaker: str | None = None
    description: str
    status: UnitStatus = "success"
    chart_set: str
    representations: list[RepresentationModel] = Field(default_factory=list)
    evidence_sha256: str | None = None
    evidence_rel_path: str | None = None
    request_hash: str | None = None
    prompt_version: str | None = None
    model: str | None = None
    model_selection_source: str | None = None
    reused: bool = False
    error_code: str | None = None
    error_message_safe: str | None = None

    @field_validator("description")
    @classmethod
    def _limit_description(cls, value: str) -> str:
        text = (value or "").strip()
        if len(text) > DEFAULT_MAX_DESCRIPTION_CHARS:
            return text[:DEFAULT_MAX_DESCRIPTION_CHARS]
        return text


class IndexEntry(BaseModel):
    chart_key: str
    logical_chart_id: str
    viz_id: str
    status: UnitStatus
    description_rel: str | None = None
    markdown_rel: str | None = None
    representations: list[RepresentationModel] = Field(default_factory=list)
    evidence_sha256: str | None = None
    request_hash: str | None = None
    reused: bool = False
    error_code: str | None = None
    error_message_safe: str | None = None


class ChartDescriptionsIndex(BaseModel):
    schema_id: Literal["transcriptx.chart_descriptions_index.v1"] = SCHEMA_INDEX
    generation_id: str
    chart_set: str
    inventory_snapshot_sha256: str
    entries: list[IndexEntry] = Field(default_factory=list)


class OutcomeCounts(BaseModel):
    selected: int = 0
    succeeded: int = 0
    skipped: int = 0
    failed: int = 0
    reused: int = 0
    llm_calls: int = 0
    circuit_trips: int = 0


class ChartDescriptionsOutcome(BaseModel):
    schema_id: Literal["transcriptx.chart_descriptions_outcome.v1"] = SCHEMA_OUTCOME
    generation_id: str
    overall_status: OverallStatus
    chart_set: str
    inventory_snapshot_sha256: str
    counts: OutcomeCounts = Field(default_factory=OutcomeCounts)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    error_code: str | None = None
    error_message_safe: str | None = None
    duration_seconds: float | None = None


class ActivePointer(BaseModel):
    schema_id: Literal["transcriptx.chart_descriptions_active.v1"] = SCHEMA_ACTIVE
    generation_id: str
    attempt_epoch: str
    overall_status: OverallStatus
    committed_at: str
    inventory_snapshot_sha256: str = ""
    chart_set: str = "all"


class AttemptEpoch(BaseModel):
    schema_id: Literal["transcriptx.chart_descriptions_attempt.v1"] = SCHEMA_ATTEMPT
    attempt_epoch: str
    generation_id: str
    started_at: str


class CommitEnvelope(BaseModel):
    schema_id: Literal["transcriptx.chart_descriptions_commit.v1"] = SCHEMA_COMMIT
    generation_id: str
    attempt_epoch: str
    committed_at: str
    overall_status: OverallStatus
    inventory_snapshot_sha256: str
    chart_set: str
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
