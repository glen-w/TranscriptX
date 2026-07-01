"""Pydantic schema for analysis.pauses."""

from pydantic import BaseModel, Field


class PausesSettingsModel(BaseModel):
    min_long_pause_seconds: float = Field(default=2.0)
    post_question_multiplier: float = Field(default=1.5)
    percentile_long_pause: float = Field(default=0.95)
