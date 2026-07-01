"""Pydantic schema for analysis.analysis_legacy_semantic settings."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AnalysisLegacySemanticSettingsModel(BaseModel):
    """Partial analysis.* scalar fields for analysis_legacy_semantic."""

    semantic_similarity_threshold: float = Field(default=0.7)
    cross_speaker_similarity_threshold: float = Field(default=0.6)
    repetition_time_window: float = Field(default=300.0)
    cross_speaker_time_window: float = Field(default=600.0)
    semantic_model_name: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    clustering_eps: float = Field(default=0.3)
    clustering_min_samples: int = Field(default=2)
    max_segments_for_semantic: int = Field(default=1000)
    max_segments_per_speaker: int = Field(default=200)
    max_segments_for_cross_speaker: int = Field(default=500)
    use_quality_filtering: bool = Field(default=True)
    min_segment_quality_score: float = Field(default=0.0)
    quality_filtering_profile: str = Field(default="balanced")
    semantic_similarity_method: str = Field(default="simple")
    quality_weights_override: dict[str, float] | None = Field(default=None)
    quality_thresholds_override: dict[str, Any] | None = Field(default=None)
    quality_indicators_override: dict[str, list[str]] | None = Field(default=None)
    max_semantic_comparisons: int = Field(default=50000)
    semantic_timeout_seconds: int = Field(default=300)
    semantic_batch_size: int = Field(default=64)
    semantic_progress_log_interval_seconds: float = Field(default=60.0)
    module_progress_log_interval_seconds: float = Field(default=60.0)
    output_formats: list[str] = Field(default_factory=lambda: ["json", "csv", "png"])
    analysis_mode: str = Field(default="quick")
    include_legacy_modules: bool = Field(default=False)
