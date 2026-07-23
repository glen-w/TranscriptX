"""Committed artifact schema for llm_custom_qa."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from transcriptx.core.analysis.llm_custom_qa.constants import (
    MODULE_NAME,
    MODULE_VERSION,
    SCHEMA_ID,
)
from transcriptx.core.analysis.llm_custom_qa.errors import (
    CustomQAArtifactValidationError,
)
from transcriptx.core.analysis.llm_custom_qa.resolve import questions_hash_for

ModelAbstainReason = Literal[
    "insufficient_evidence",
    "ambiguous",
    "out_of_scope",
    "not_in_provided_excerpt",
]

SystemUnavailableReason = Literal[
    "response_incomplete",
    "response_invalid",
    "grounding_failed",
    "input_truncated",
]

AnswerRowStatus = Literal["answered", "abstained", "unavailable"]

Outcome = Literal[
    "empty_questions",
    "answered",
    "all_abstained",
    "all_unavailable",
    "mixed",
]

ResolvedFrom = Literal["library", "request", "explicit_empty"]


class CitationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quote: str
    segment_indexes: list[int] = Field(min_length=1)
    start_time: Optional[float] = None
    end_time: Optional[float] = None


class RowGroundingDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quotes_requested: int = 0
    quotes_grounded: int = 0
    citations_emitted: int = 0
    citations_truncated: int = 0
    cross_segment_citations: int = 0


class ArtifactAnswerRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_index: int
    question: str
    status: AnswerRowStatus
    answer: Optional[str] = None
    abstain_reason: Optional[ModelAbstainReason] = None
    system_reason: Optional[SystemUnavailableReason] = None
    confidence: Optional[float] = None
    citations: list[CitationModel] = Field(default_factory=list)
    grounding: RowGroundingDiagnostics = Field(
        default_factory=RowGroundingDiagnostics
    )


class DiagnosticsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers_over_limit: int = 0
    extra_or_duplicate_rows_dropped: int = 0
    response_incomplete_count: int = 0
    response_invalid_count: int = 0
    grounding_failed_count: int = 0
    input_truncated_overrides: int = 0
    absence_detector_hits: int = 0
    citations_total: int = 0
    cross_segment_citations_total: int = 0


class InputCoverageModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    input_chars_total: int = 0
    input_chars_used: int = 0
    input_coverage_ratio: Optional[float] = None
    truncated: bool = False
    segments_total: int = 0
    segments_used: int = 0
    segments_omitted_empty: int = 0
    segments_omitted_invalid: int = 0
    partial_final_segment: bool = False
    transcript_fingerprint: Optional[str] = None
    bounded_input_fingerprint: Optional[str] = None


class ProvenanceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    module: str = MODULE_NAME
    prompt_version: str
    schema_id: str = SCHEMA_ID
    module_version: str = MODULE_VERSION
    provider: Optional[str] = None
    model: Optional[str] = None
    seed: Optional[int] = None
    temperature: Optional[float] = None
    max_output_tokens: Optional[int] = None
    generation_options: dict[str, Any] = Field(default_factory=dict)
    llm_request_sha256: Optional[str] = None
    questions_hash: str
    resolved_from: ResolvedFrom
    questions_requested: list[str]
    empty_run: bool = False
    transcriptx_version: Optional[str] = None
    cache_key: Optional[str] = None
    attempt_index: Optional[int] = None
    model_digest: Optional[str] = None
    model_selection_source: Optional[str] = None


class LLMCustomQAArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_id: str = SCHEMA_ID
    module: str = MODULE_NAME
    module_version: str = MODULE_VERSION
    questions_requested: list[str]
    questions_hash: str
    answers: list[ArtifactAnswerRow]
    diagnostics: DiagnosticsModel
    input_coverage: InputCoverageModel
    outcome: Outcome
    provenance: ProvenanceModel
    cache_key: Optional[str] = None

    @model_validator(mode="after")
    def _invariants(self) -> "LLMCustomQAArtifact":
        expected_hash = questions_hash_for(tuple(self.questions_requested))
        if self.questions_hash != expected_hash:
            raise ValueError("questions_hash does not match questions_requested")
        n = len(self.questions_requested)
        if len(self.answers) != n:
            raise ValueError("answers length must equal questions_requested length")
        for i, row in enumerate(self.answers):
            if row.question_index != i:
                raise ValueError("answers must be ordered by question_index 0..n-1")
            if row.question != self.questions_requested[i]:
                raise ValueError("answer.question must match questions_requested")
        if self.cache_key != self.provenance.cache_key:
            raise ValueError("top-level cache_key must match provenance.cache_key")
        if self.provenance.questions_hash != self.questions_hash:
            raise ValueError("provenance.questions_hash mismatch")
        if list(self.provenance.questions_requested) != list(self.questions_requested):
            raise ValueError("provenance.questions_requested mismatch")
        return self


def empty_diagnostics() -> dict[str, Any]:
    return DiagnosticsModel().model_dump()


def empty_input_coverage(*, empty_run: bool = False) -> dict[str, Any]:
    """Zero-input / empty-questions coverage: ratio is null, not 1.0."""
    return InputCoverageModel(
        input_chars_total=0,
        input_chars_used=0,
        input_coverage_ratio=None if empty_run else None,
        truncated=False,
    ).model_dump()


def validate_artifact(
    payload: dict[str, Any],
    *,
    questions_requested: list[str] | tuple[str, ...] | None = None,
    questions_hash: str | None = None,
) -> dict[str, Any]:
    """Validate artifact against schema and optional expected questions."""
    try:
        art = LLMCustomQAArtifact.model_validate(payload)
    except Exception as exc:
        raise CustomQAArtifactValidationError(
            f"Artifact validation failed: {exc}",
            error_context={"reason": "schema"},
        ) from exc
    if questions_requested is not None:
        if list(art.questions_requested) != list(questions_requested):
            raise CustomQAArtifactValidationError(
                "Artifact questions_requested mismatch",
                error_context={"reason": "questions_mismatch"},
            )
    if questions_hash is not None and art.questions_hash != questions_hash:
        raise CustomQAArtifactValidationError(
            "Artifact questions_hash mismatch",
            error_context={"reason": "hash_mismatch"},
        )
    return art.model_dump(mode="json")


def compute_outcome(answers: list[dict[str, Any]], *, empty: bool) -> Outcome:
    if empty:
        return "empty_questions"
    if not answers:
        return "empty_questions"
    statuses = [a.get("status") for a in answers]
    if all(s == "answered" for s in statuses):
        return "answered"
    if all(s == "abstained" for s in statuses):
        return "all_abstained"
    if all(s == "unavailable" for s in statuses):
        return "all_unavailable"
    if any(s == "answered" for s in statuses) and all(
        s in ("answered", "abstained", "unavailable") for s in statuses
    ):
        if not any(s == "answered" for s in statuses):
            return "mixed"
        if any(s != "answered" for s in statuses):
            return "mixed"
        return "answered"
    return "mixed"
