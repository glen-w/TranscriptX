"""Pydantic schema for analysis.analysis_entity settings."""

from __future__ import annotations


from pydantic import BaseModel, Field


class AnalysisEntitySettingsModel(BaseModel):
    """Partial analysis.* scalar fields for analysis_entity."""

    entity_min_mentions: int = Field(default=2)
    entity_types: list[str] = Field(
        default_factory=lambda: ["PERSON", "ORG", "GPE", "LOC"]
    )
    entity_sentiment_threshold: float = Field(default=0.05)
