"""Pydantic schema for analysis.tag_extraction."""

from pydantic import BaseModel, Field


class TagExtractionSettingsModel(BaseModel):
    early_window_seconds: int = Field(default=60)
    early_segments: int = Field(default=10)
    min_confidence: float = Field(default=0.6)
