"""Pydantic schema for analysis.quick_analysis_settings preset."""

from pydantic import BaseModel, Field


class QuickAnalysisSettingsModel(BaseModel):
    use_lightweight_models: bool = Field(default=True)
    semantic_method: str = Field(default="simple")
    max_segments_for_semantic: int = Field(default=800)
    max_semantic_comparisons: int = Field(default=15000)
    ner_use_light_model: bool = Field(default=False)
    ner_max_segments: int = Field(default=2000)
    skip_advanced_semantic: bool = Field(default=True)
    skip_geocoding: bool = Field(default=False)
    reduced_chart_generation: bool = Field(default=True)
    semantic_profile: str = Field(default="balanced")
