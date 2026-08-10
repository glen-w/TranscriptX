"""Pydantic schema for analysis.insight_eligibility."""

from pydantic import BaseModel, Field


class InsightEligibilitySettingsModel(BaseModel):
    """Shared content-phrase eligibility thresholds for downstream modules."""

    min_score: float = Field(default=0.28, ge=0.0, le=1.0)
    min_frequency: int = Field(default=2, ge=1, le=20)
    require_spread_or_recurrence_for_singletons: bool = Field(default=True)
