"""Pydantic schema for analysis.llm_custom_qa settings."""

from __future__ import annotations

from pydantic import BaseModel, Field

from transcriptx.core.config.models.llm_summary import LLMSummaryEffort

# Keep equal to analysis.llm_custom_qa.constants.MAX_ANSWER_CHARS (parity-tested).
# Layers cannot cross-import this constant.
_MAX_ANSWER_CHARS_DEFAULT = 800

_HIDDEN = {"sensitivity": "hidden"}


class LLMCustomQASettingsModel(BaseModel):
    """Settings for the llm_custom_qa analysis module."""

    effort: LLMSummaryEffort = Field(
        default="high",
        description=(
            "Effort tier for llm_custom_qa when llm.provider is ollama. "
            "Controls max_input_chars, request_timeout, and max_output_tokens."
        ),
    )
    saved_questions: list[str] = Field(
        default_factory=list,
        description="Project question library (edited via Settings → Questions).",
        json_schema_extra=_HIDDEN,
    )
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
