"""Pydantic schema for analysis.llm_summary settings."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

LLMSummaryEffort = Literal["low", "medium", "high", "max"]


class LLMSummarySettingsModel(BaseModel):
    """Effort tier for the llm_summary analysis module (Ollama path only)."""

    effort: LLMSummaryEffort = Field(
        default="high",
        description=(
            "Summary effort tier for llm_summary when llm.provider is ollama. "
            "Controls max_input_chars, request_timeout, and max_output_tokens "
            "for that module only. Medium and above are completeness-oriented."
        ),
    )
