"""Pydantic schema for analysis.chart_descriptions settings."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ChartSet = Literal["all", "transcript_group", "overview_only"]


class ChartDescriptionsSettingsModel(BaseModel):
    """Finalize-phase per-chart LLM narrative generation."""

    enabled: bool = Field(
        default=True,
        description=(
            "When true (default), the finalize-phase chart_descriptions step "
            "runs if the module is selected and LLM is enabled."
        ),
    )
    chart_set: ChartSet = Field(
        default="all",
        description=(
            "Which logical charts receive LLM descriptions: all, "
            "transcript_group (primary run charts only), or overview_only."
        ),
    )
    max_description_chars: int = Field(
        default=1200,
        ge=64,
        le=8000,
        description="Maximum length of a validated LLM description string.",
    )
    request_timeout: float = Field(
        default=120.0,
        ge=5.0,
        description="Per-chart LLM request timeout in seconds.",
    )
    max_retries: int = Field(
        default=1,
        ge=0,
        le=5,
        description="Retries per chart after a transient provider failure.",
    )
    circuit_breaker_failures: int = Field(
        default=3,
        ge=1,
        le=50,
        description=(
            "Consecutive systemic provider failures before stopping further "
            "LLM calls for this generation."
        ),
    )
