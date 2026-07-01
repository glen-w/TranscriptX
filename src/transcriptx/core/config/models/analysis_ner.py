"""Pydantic schema for analysis.analysis_ner settings."""

from __future__ import annotations


from pydantic import BaseModel, Field


class AnalysisNerSettingsModel(BaseModel):
    """Partial analysis.* scalar fields for analysis_ner."""

    ner_labels: list[str] = Field(
        default_factory=lambda: ["PERSON", "ORG", "GPE", "LOC", "DATE", "TIME", "MONEY"]
    )
    ner_min_confidence: float = Field(default=0.5)
    ner_include_geocoding: bool = Field(default=True)
    ner_use_light_model: bool = Field(default=False)
    ner_max_segments: int = Field(default=5000)
    ner_batch_size: int = Field(default=100)
