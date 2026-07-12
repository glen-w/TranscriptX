"""Pydantic schema for analysis.llm_speaker_summary settings."""

from __future__ import annotations

from pydantic import BaseModel, Field

from transcriptx.core.config.models.llm_summary import LLMSummaryEffort


class LLMSpeakerSummarySettingsModel(BaseModel):
    """Effort tier for the llm_speaker_summary analysis module (Ollama path only)."""

    effort: LLMSummaryEffort = Field(
        default="high",
        description=(
            "Summary effort tier for llm_speaker_summary when llm.provider is ollama. "
            "Controls max_input_chars, request_timeout, and max_output_tokens "
            "for that module only. Medium and above are completeness-oriented."
        ),
    )
