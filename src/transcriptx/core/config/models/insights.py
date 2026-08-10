"""Pydantic schema for analysis.insights."""

from pydantic import BaseModel, Field


class InsightsCountsModel(BaseModel):
    top_themes: int = Field(default=8, ge=1, le=40)
    top_recurring_ideas: int = Field(default=8, ge=1, le=40)
    top_notable_moments: int = Field(default=8, ge=1, le=40)
    overview_theme_cap: int = Field(default=5, ge=1, le=20)


class InsightsSettingsModel(BaseModel):
    """Content-first insights composer settings."""

    enabled: bool = Field(default=True)
    counts: InsightsCountsModel = Field(default_factory=InsightsCountsModel)
    min_theme_score: float = Field(default=0.28, ge=0.0, le=1.0)
    min_themes_for_signal: int = Field(default=2, ge=1, le=10)
    topic_boost: float = Field(default=0.05, ge=0.0, le=0.5)
