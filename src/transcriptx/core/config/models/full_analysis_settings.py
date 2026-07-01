"""Pydantic schema for analysis.full_analysis_settings preset."""

from pydantic import BaseModel, Field


class FullAnalysisSettingsModel(BaseModel):
    use_lightweight_models: bool = Field(default=False)
    semantic_method: str = Field(default="advanced")
    max_segments_for_semantic: int = Field(default=1000)
    max_semantic_comparisons: int = Field(default=30000)
    max_segments_per_speaker: int = Field(default=400)
    max_segments_for_cross_speaker: int = Field(default=1000)
    ner_use_light_model: bool = Field(default=False)
    ner_max_segments: int = Field(default=5000)
    skip_advanced_semantic: bool = Field(default=False)
    skip_geocoding: bool = Field(default=False)
    reduced_chart_generation: bool = Field(default=False)
    semantic_profile: str = Field(default="balanced")
