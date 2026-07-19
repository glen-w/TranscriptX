"""Pydantic schema for analysis.group_llm_synthesis settings."""

from __future__ import annotations

from pydantic import BaseModel, Field

from transcriptx.core.config.models.llm_summary import LLMSummaryEffort

GroupLLMSynthesisEffort = LLMSummaryEffort


class GroupLLMSynthesisSettingsModel(BaseModel):
    """Cross-session synthesis over collected member LLM summaries."""

    enabled: bool = Field(
        default=True,
        description=(
            "When true (default), group finalize synthesises cross-session "
            "global and per-speaker summaries from collected member artifacts "
            "when LLM (Ollama) is available."
        ),
    )
    effort: GroupLLMSynthesisEffort = Field(
        default="high",
        description=(
            "Effort tier for group LLM synthesis Ollama calls. Resolves "
            "effective max_input_chars, request_timeout, and max_output_tokens "
            "for these calls only without mutating global llm.* settings."
        ),
    )
