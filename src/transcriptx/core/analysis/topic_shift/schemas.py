"""Pydantic output envelopes for topic_shift deterministic artifacts."""

from __future__ import annotations

from typing import Any, Literal, Mapping, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from transcriptx.core.analysis.topic_shift.semantics import SCHEMA_VERSION

AnalyticalStatusLiteral = Literal[
    "success",
    "no_shift_detected",
    "insufficient_content",
    "unsupported_language",
    "backend_unavailable",
    "invalid_input",
]

BoundaryStatusLiteral = Literal[
    "inferred",
    "no_shift_detected",
    "abstained",
]


class BoundaryStrengthModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_distance: float
    local_prominence: float
    decision_threshold: float
    normalized_strength: float
    backend: str


class TopicShiftEventEvidenceModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    raw_distance: float
    local_prominence: float
    decision_threshold: float
    normalized_strength: float
    backend: str
    boundary_window_index: int
    semantics_version: str


class TopicShiftEventModel(BaseModel):
    """Validated Event-shaped boundary (shared Event fields + evidence)."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    kind: Literal["topic_shift"] = "topic_shift"
    time_start: float
    time_end: float
    speaker: Optional[str] = None
    segment_start_idx: Optional[int] = None
    segment_end_idx: Optional[int] = None
    severity: float
    score: Optional[float] = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    links: list[dict[str, Any]] = Field(default_factory=list)


class CoverageSpanModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    span_id: str
    index: int
    time_start: float
    time_end: float
    segment_start_idx: int
    segment_end_idx: int  # inclusive
    label: str
    keyword_hints: list[str] = Field(default_factory=list)
    inferred: bool
    boundary_status: BoundaryStatusLiteral
    leading_boundary_id: Optional[str] = None
    viewer_target_source_index: int
    analytical_status: AnalyticalStatusLiteral
    backend: str
    semantics_version: str
    provenance: dict[str, Any] = Field(default_factory=dict)


class SpansEnvelopeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    semantics_version: str
    transcript_identity: str
    deterministic_generation_id: str
    analytical_status: AnalyticalStatusLiteral
    backend: str
    coverage_spans: list[CoverageSpanModel]
    span_count: int

    @field_validator("span_count")
    @classmethod
    def _count_matches(cls, v: int, info: Any) -> int:
        spans = info.data.get("coverage_spans")
        if spans is not None and v != len(spans):
            raise ValueError("span_count must equal len(coverage_spans)")
        return v


class EventsEnvelopeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    semantics_version: str
    transcript_identity: str
    deterministic_generation_id: str
    analytical_status: AnalyticalStatusLiteral
    backend: str
    event_count: int
    events: list[TopicShiftEventModel]

    @field_validator("event_count")
    @classmethod
    def _count_matches(cls, v: int, info: Any) -> int:
        events = info.data.get("events")
        if events is not None and v != len(events):
            raise ValueError("event_count must equal len(events)")
        return v


class StatsEnvelopeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    schema_version: str = SCHEMA_VERSION
    semantics_version: str
    transcript_identity: str
    deterministic_generation_id: str
    analytical_status: AnalyticalStatusLiteral
    backend: str
    model_name: Optional[str] = None
    n_shifts: int = 0
    shifts_per_hour: Optional[float] = None
    median_span_duration: Optional[float] = None
    longest_span_duration: Optional[float] = None
    valid_duration_seconds: Optional[float] = None
    language_resolution: Optional[str] = None
    language_code: Optional[str] = None
    limited_language_support: bool = False
    windowing: dict[str, Any] = Field(default_factory=dict)
    thresholds: dict[str, Any] = Field(default_factory=dict)
    coverage_map: dict[str, Any] = Field(default_factory=dict)
    provenance_compatibility_key: str = ""


class EnrichmentEntryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    span_id: str
    title: Optional[str] = None
    summary: Optional[str] = None
    key_points: list[str] = Field(default_factory=list)
    title_source: str = "deterministic_fallback"
    error_category: Optional[str] = None


class EnrichmentEnvelopeModel(BaseModel):
    """Validated enrichment sidecar (unique span_ids required)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str
    prompt_version: str
    outcome: Literal["success", "partial", "skipped", "failed"]
    skip_reason: Optional[str] = None
    deterministic_generation_id: str
    deterministic_digest: str
    model: Optional[str] = None
    selection_source: Optional[str] = None
    entries: list[EnrichmentEntryModel] = Field(default_factory=list)
    overall_summary: Optional[str] = None
    ui_mode: str = "chapter_titles"
    analytical_status_hint: Optional[str] = None

    @field_validator("entries")
    @classmethod
    def _unique_span_ids(
        cls, entries: list[EnrichmentEntryModel]
    ) -> list[EnrichmentEntryModel]:
        seen: set[str] = set()
        for entry in entries:
            sid = str(entry.span_id or "")
            if not sid:
                raise ValueError("enrichment entries require non-empty span_id")
            if sid in seen:
                raise ValueError(f"duplicate enrichment span_id: {sid}")
            seen.add(sid)
        return entries


def validate_enrichment_payload(payload: Mapping[str, Any] | dict[str, Any]) -> dict[str, Any]:
    """Validate enrichment dict; raises ValidationError on contract breach."""
    return EnrichmentEnvelopeModel.model_validate(payload).model_dump()
