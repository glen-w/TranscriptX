"""Pydantic schema for analysis.names settings."""

from pydantic import BaseModel, Field


class AnalysisNamesSettingsModel(BaseModel):
    min_mentions: int = Field(default=1, ge=1)
    exclude_known_speakers: bool = Field(default=False)
    max_mentions_per_person: int = Field(default=50, ge=1)
