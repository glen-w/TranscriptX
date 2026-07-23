"""Parallel v2 artifact contracts — import only V2_* identities."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from transcriptx.core.analysis.llm_custom_qa.errors import (
    CustomQAArtifactValidationError,
)
from transcriptx.core.analysis.llm_custom_qa.versioning import (
    V2_CONTRACT_VERSION,
    V2_MODULE_VERSION,
    V2_SCHEMA_ID,
)

MODULE_NAME = "llm_custom_qa"

ModelAbstainReasonV2 = Literal[
    "insufficient_evidence",
    "ambiguous",
    "out_of_scope",
    "not_in_provided_excerpt",
]

SystemUnavailableReasonV2 = Literal[
    "response_incomplete",
    "response_invalid",
    "backend_absent",
    "transport_exhausted",
    "llm_budget_exhausted",
    "pass_failed",
    "evidence_unavailable",
    "input_truncated",
]

AnswerRowStatusV2 = Literal["answered", "abstained", "unavailable"]
ScopeV2 = Literal["global", "per_speaker"]
OutcomeV2 = Literal[
    "empty_questions",
    "no_scheduled_cells",
    "answered",
    "all_abstained",
    "all_unavailable",
    "mixed",
    "partial",
]
ResolvedFromV2 = Literal["library", "request", "explicit_empty"]
RouteSourceV2 = Literal["router", "fallback"]


class CitationModelV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quote: str
    segment_indexes: list[int] = Field(min_length=1)
    start_time: Optional[float] = None
    end_time: Optional[float] = None


class RowGroundingDiagnosticsV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quotes_requested: int = 0
    quotes_grounded: int = 0
    citations_emitted: int = 0
    citations_truncated: int = 0
    cross_segment_citations: int = 0
    quotes_soft_dropped: int = 0


class EvidenceUsedV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pack_ids_rendered: list[str] = Field(default_factory=list)
    pack_states: dict[str, str] = Field(default_factory=dict)
    use_transcript: bool = False
    transcript_fallback: bool = False
    chars_per_source: dict[str, int] = Field(default_factory=dict)
    fingerprints: dict[str, str] = Field(default_factory=dict)
    materialiser_versions: dict[str, str] = Field(default_factory=dict)
    rendered_format_version: str = "1"


class QuestionScopesV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    global_scope: bool = Field(alias="global")
    per_speaker: bool

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# Pydantic v2: fix duplicate model_config
class QuestionScopesModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    global_scope: bool = Field(alias="global")
    per_speaker: bool


class CanonicalQuestionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    text: str
    scopes: QuestionScopesModel


class ArtifactAnswerRowV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    question: str
    scope: ScopeV2
    speaker_key: Optional[str] = None
    status: AnswerRowStatusV2
    answer: Optional[str] = None
    reasoning: Optional[str] = None
    abstain_reason: Optional[ModelAbstainReasonV2] = None
    system_reason: Optional[SystemUnavailableReasonV2] = None
    confidence: Optional[float] = None
    citations: list[CitationModelV2] = Field(default_factory=list)
    evidence_used: EvidenceUsedV2 = Field(default_factory=EvidenceUsedV2)
    grounding: RowGroundingDiagnosticsV2 = Field(
        default_factory=RowGroundingDiagnosticsV2
    )

    @model_validator(mode="after")
    def _status_fields(self) -> "ArtifactAnswerRowV2":
        if self.scope == "global" and self.speaker_key is not None:
            raise ValueError("global rows require speaker_key=null")
        if self.scope == "per_speaker" and not self.speaker_key:
            raise ValueError("per_speaker rows require speaker_key")
        if self.status == "answered":
            if not (self.answer and str(self.answer).strip()):
                raise ValueError("answered requires non-empty answer")
            if not (self.reasoning and str(self.reasoning).strip()):
                raise ValueError("answered requires non-empty reasoning")
            if self.abstain_reason is not None or self.system_reason is not None:
                raise ValueError("answered forbids abstain_reason/system_reason")
        elif self.status == "abstained":
            if self.abstain_reason is None:
                raise ValueError("abstained requires abstain_reason")
            if self.answer is not None or self.reasoning is not None:
                raise ValueError("abstained requires answer/reasoning null")
            if self.system_reason is not None:
                raise ValueError("abstained forbids system_reason")
            if self.citations:
                raise ValueError("abstained requires empty citations")
        elif self.status == "unavailable":
            if self.system_reason is None:
                raise ValueError("unavailable requires system_reason")
            if self.answer is not None or self.reasoning is not None:
                raise ValueError("unavailable requires answer/reasoning null")
            if self.abstain_reason is not None:
                raise ValueError("unavailable forbids abstain_reason")
            if self.citations:
                raise ValueError("unavailable requires empty citations")
        return self


class SpeakerAnswersBlockV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    speaker: str
    speaker_key: str
    grouping_keys: list[str] = Field(default_factory=list)
    answers: list[ArtifactAnswerRowV2] = Field(default_factory=list)


class RouteEntryV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    pack_ids: list[str] = Field(default_factory=list)
    use_transcript: bool = True
    source: RouteSourceV2 = "fallback"


class EvidencePlanV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    routes: list[RouteEntryV2] = Field(default_factory=list)
    routes_hash: str = ""
    packs_available: list[str] = Field(default_factory=list)
    packs_missing: list[str] = Field(default_factory=list)
    packs_invalid: list[str] = Field(default_factory=list)
    packs_incompatible: list[str] = Field(default_factory=list)


class EffectivePlanSummaryV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expanded_pack_ids: list[str] = Field(default_factory=list)
    catalog_version: str = "1"
    speaker_keys: list[str] = Field(default_factory=list)
    speaker_limit: int = 0
    scheduler_version: str = "1"
    fingerprint_refs: dict[str, str] = Field(default_factory=dict)


class DiagnosticsModelV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers_over_limit: int = 0
    extra_or_duplicate_rows_dropped: int = 0
    response_incomplete_count: int = 0
    response_invalid_count: int = 0
    soft_quote_drops: int = 0
    input_truncated_overrides: int = 0
    absence_detector_hits: int = 0
    citations_total: int = 0
    cross_segment_citations_total: int = 0
    speakers_omitted_by_cap: list[str] = Field(default_factory=list)
    speaker_alias_collisions: int = 0
    llm_budget_exhausted_cells: int = 0
    alias_update_warnings: int = 0


class InputCoverageModelV2(BaseModel):
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


class ProvenanceModelV2(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    module: str = MODULE_NAME
    schema_id: str = V2_SCHEMA_ID
    module_version: str = V2_MODULE_VERSION
    contract_version: str = V2_CONTRACT_VERSION
    router_prompt_version: Optional[str] = None
    answer_prompt_version: Optional[str] = None
    repair_prompt_version: Optional[str] = None
    provider: Optional[str] = None
    router_model: Optional[str] = None
    answer_model: Optional[str] = None
    router_generation_options: dict[str, Any] = Field(default_factory=dict)
    answer_generation_options: dict[str, Any] = Field(default_factory=dict)
    seed: Optional[int] = None
    questions_hash: str = ""
    question_order: list[str] = Field(default_factory=list)
    resolved_from: ResolvedFromV2 = "library"
    empty_run: bool = False
    transcriptx_version: Optional[str] = None
    cache_key: Optional[str] = None
    run_execution_id: Optional[str] = None
    attempt_index: Optional[int] = None
    model_digest: Optional[str] = None
    model_selection_source: Optional[str] = None
    logical_llm_calls: int = 0
    http_attempts: int = 0


class LLMCustomQAArtifactV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_id: str = V2_SCHEMA_ID
    module: str = MODULE_NAME
    module_version: str = V2_MODULE_VERSION
    contract_version: str = V2_CONTRACT_VERSION
    questions_requested: list[CanonicalQuestionModel]
    question_order: list[str]
    questions_hash: str
    answers: list[ArtifactAnswerRowV2] = Field(default_factory=list)
    speaker_answers: list[SpeakerAnswersBlockV2] = Field(default_factory=list)
    evidence_plan: EvidencePlanV2 = Field(default_factory=EvidencePlanV2)
    effective_plan_summary: EffectivePlanSummaryV2 = Field(
        default_factory=EffectivePlanSummaryV2
    )
    diagnostics: DiagnosticsModelV2 = Field(default_factory=DiagnosticsModelV2)
    input_coverage: InputCoverageModelV2 = Field(default_factory=InputCoverageModelV2)
    outcome: OutcomeV2
    provenance: ProvenanceModelV2
    cache_key: Optional[str] = None

    @model_validator(mode="after")
    def _invariants(self) -> "LLMCustomQAArtifactV2":
        if self.schema_id != V2_SCHEMA_ID:
            raise ValueError("schema_id must be V2_SCHEMA_ID")
        if self.contract_version != V2_CONTRACT_VERSION:
            raise ValueError("contract_version mismatch")
        ids = [q.question_id for q in self.questions_requested]
        if list(self.question_order) != ids:
            # question_order is display order matching questions_requested order
            if set(self.question_order) != set(ids):
                raise ValueError("question_order must reference questions_requested")
            if len(self.question_order) != len(ids):
                raise ValueError("question_order length mismatch")
        if self.cache_key != self.provenance.cache_key:
            raise ValueError("top-level cache_key must match provenance.cache_key")
        for row in self.answers:
            if row.scope != "global":
                raise ValueError("answers[] must be global scope")
        for block in self.speaker_answers:
            for row in block.answers:
                if row.scope != "per_speaker":
                    raise ValueError("speaker_answers rows must be per_speaker")
                if row.speaker_key != block.speaker_key:
                    raise ValueError("speaker_key mismatch in speaker_answers")
        return self


def compute_outcome_v2(
    *,
    empty_questions: bool,
    scheduled_statuses: list[str],
) -> OutcomeV2:
    """Executable outcome truth table (Stage 0 freeze)."""
    if empty_questions:
        return "empty_questions"
    if not scheduled_statuses:
        return "no_scheduled_cells"
    statuses = list(scheduled_statuses)
    if all(s == "answered" for s in statuses):
        return "answered"
    if all(s == "abstained" for s in statuses):
        return "all_abstained"
    if all(s == "unavailable" for s in statuses):
        return "all_unavailable"
    has_unavail = any(s == "unavailable" for s in statuses)
    has_model = any(s in ("answered", "abstained") for s in statuses)
    if has_unavail and has_model:
        return "partial"
    if has_model and not has_unavail:
        return "mixed"
    return "mixed"


def validate_artifact_v2(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        art = LLMCustomQAArtifactV2.model_validate(payload)
    except Exception as exc:
        raise CustomQAArtifactValidationError(
            f"V2 artifact validation failed: {exc}",
            error_context={"reason": "schema_v2"},
        ) from exc
    return art.model_dump(mode="json", by_alias=True)


def collect_scheduled_statuses(artifact: MappingLike) -> list[str]:
    statuses: list[str] = []
    for row in artifact.get("answers") or []:
        if isinstance(row, dict) and row.get("status"):
            statuses.append(str(row["status"]))
    for block in artifact.get("speaker_answers") or []:
        if not isinstance(block, dict):
            continue
        for row in block.get("answers") or []:
            if isinstance(row, dict) and row.get("status"):
                statuses.append(str(row["status"]))
    return statuses


# Typing helper without importing Mapping from typing twice in signature above
from typing import Mapping as MappingLike  # noqa: E402
