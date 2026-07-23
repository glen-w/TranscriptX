"""Pydantic schema for analysis.llm_action_items settings."""

from __future__ import annotations

from pydantic import BaseModel, Field

from transcriptx.core.config.models.llm_summary import LLMSummaryEffort


class LLMActionItemsSettingsModel(BaseModel):
    """Effort tier for the llm_action_items analysis module (Ollama path only)."""

    effort: LLMSummaryEffort = Field(
        default="high",
        description=(
            "Effort tier for llm_action_items when llm.provider is ollama. "
            "Controls max_input_chars, request_timeout, and max_output_tokens "
            "for that module only. Defaults to high because action extraction "
            "is completeness-oriented across long meetings."
        ),
    )
    coerce_v1_artifacts: bool = Field(
        default=False,
        description=(
            "When true, in-memory coerce v1 llm_action_items artifacts to "
            "record_type=action_item with provenance.compat=v1_coerced for "
            "presentation and group aggregation. When false, v1 artifacts are "
            "not treated as native v2 and mixed-version group members fail "
            "explicitly. Does not rewrite on-disk artifacts."
        ),
    )
