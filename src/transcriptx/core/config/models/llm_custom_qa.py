"""Pydantic schema for analysis.llm_custom_qa settings."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from transcriptx.core.config.models.llm_summary import LLMSummaryEffort

# Keep equal to analysis.llm_custom_qa.constants.MAX_ANSWER_CHARS (parity-tested).
# Layers cannot cross-import this constant.
_MAX_ANSWER_CHARS_DEFAULT = 800

_HIDDEN = {"sensitivity": "hidden"}


class QuestionScopesSettingsModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    global_scope: bool = Field(alias="global")
    per_speaker: bool

    @model_validator(mode="after")
    def _at_least_one(self) -> "QuestionScopesSettingsModel":
        if not self.global_scope and not self.per_speaker:
            raise ValueError("At least one scope must be true")
        return self


class SavedQuestionSettingsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    scopes: QuestionScopesSettingsModel


def _migrate_saved_questions(raw: Any) -> list[dict[str, Any]]:
    """Idempotent load-time migration: list[str] → structured; reject mixed."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise TypeError("saved_questions must be a list")
    kinds: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, str):
            kinds.add("str")
            out.append(
                {
                    "text": item,
                    "scopes": {"global": True, "per_speaker": False},
                }
            )
        elif isinstance(item, dict):
            kinds.add("obj")
            out.append(item)
        else:
            raise TypeError("saved_questions entries must be str or object")
    if len(kinds) > 1:
        raise ValueError("Mixed string/object saved_questions lists are rejected")
    return out


class LLMCustomQASettingsModel(BaseModel):
    """Settings for the llm_custom_qa analysis module."""

    model_config = ConfigDict(extra="forbid")

    effort: LLMSummaryEffort = Field(
        default="high",
        description=(
            "Effort tier for llm_custom_qa when llm.provider is ollama. "
            "Controls max_input_chars, request_timeout, and max_output_tokens."
        ),
    )
    saved_questions: list[SavedQuestionSettingsModel] = Field(
        default_factory=list,
        description="Project question library (edited via Settings → Questions).",
        json_schema_extra=_HIDDEN,
    )
    evidence_pack_ids: Optional[list[str]] = Field(
        default=None,
        description=(
            "Packs eligible for routing. null = all present and future catalog packs; "
            "[] = packs disabled; list = explicit enable set."
        ),
    )
    include_transcript: bool = Field(
        default=True,
        description="Allow transcript excerpt in answer prompts.",
    )
    routing_enabled: bool = Field(
        default=True,
        description="If false, skip router and use all available enabled packs.",
    )
    max_packs_per_question: int = Field(default=3, ge=0, le=16)
    max_reasoning_chars: int = Field(default=600, ge=50, le=4000)
    max_eligible_speakers: int = Field(default=12, ge=0, le=64)
    max_speaker_question_cells: int = Field(default=48, ge=0, le=512)
    max_llm_calls_per_run: int = Field(default=16, ge=1, le=64)
    max_library_questions: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Maximum questions stored in the project library.",
    )
    max_library_total_question_chars: int = Field(
        default=20000,
        ge=1,
        le=100000,
        description="Maximum total characters across library questions.",
    )
    max_questions_per_run: int = Field(
        default=8,
        ge=1,
        le=8,
        description="Maximum questions answered in a single analysis run.",
    )
    max_question_chars: int = Field(
        default=500,
        ge=1,
        le=2000,
        description="Maximum characters per question (library and run).",
    )
    max_run_total_question_chars: int = Field(
        default=4000,
        ge=1,
        le=16000,
        description="Maximum total characters across questions in one run.",
    )
    max_answer_chars: int = Field(
        default=_MAX_ANSWER_CHARS_DEFAULT,
        ge=100,
        le=4000,
        description="Maximum characters per model answer (oversize rows rejected).",
    )

    @field_validator("saved_questions", mode="before")
    @classmethod
    def _migrate_questions(cls, value: Any) -> Any:
        return _migrate_saved_questions(value)

    @field_validator("evidence_pack_ids", mode="before")
    @classmethod
    def _normalize_pack_ids(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, list):
            raise TypeError("evidence_pack_ids must be a list or null")
        return [str(x) for x in value if isinstance(x, str)]
