"""Pydantic schema for analysis.acts settings."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ActsSettingsModel(BaseModel):
    """Canonical field definitions for dialogue acts classification configuration."""

    method: Literal["rules", "ml", "both"] = Field(
        default="both",
        description="Classification strategy: rules, machine learning, or both.",
    )
    use_context: bool = Field(
        default=True,
        description="Include neighbouring segments as classification context.",
    )
    context_window_size: int = Field(
        default=3,
        ge=1,
        description="Number of neighbouring segments in each context direction.",
    )
    context_window_type: Literal["fixed", "dynamic", "sliding"] = Field(
        default="sliding",
        description="How the context window is constructed around each segment.",
    )
    include_speaker_info: bool = Field(
        default=True,
        description="Include speaker identity in context features.",
    )
    include_timing_info: bool = Field(
        default=False,
        description="Include timing deltas in context features.",
    )
    min_confidence: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum confidence to accept a classification.",
    )
    high_confidence_threshold: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Threshold for high-confidence classifications.",
    )
    ensemble_weight_transformer: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Ensemble weight for transformer-based scores.",
    )
    ensemble_weight_ml: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Ensemble weight for traditional ML scores.",
    )
    ensemble_weight_rules: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Ensemble weight for rule-based scores.",
    )
    ml_model_name: str = Field(
        default="bert-base-uncased",
        description="Hugging Face model id for ML classification.",
    )
    ml_use_gpu: bool = Field(
        default=False,
        description="Use GPU for ML classification when available.",
    )
    ml_batch_size: int = Field(
        default=32,
        ge=1,
        description="Batch size for ML inference.",
    )
    ml_max_length: int = Field(
        default=512,
        ge=1,
        description="Maximum token length for ML model input.",
    )
    rules_use_enhanced_patterns: bool = Field(
        default=True,
        description="Use enhanced regex patterns in rule-based classification.",
    )
    rules_use_fallback_logic: bool = Field(
        default=True,
        description="Apply fallback heuristics when rules are inconclusive.",
    )
    rules_confidence_boost_exact_match: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Confidence boost applied on exact pattern matches.",
    )
    rules_context_boost_factor: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Confidence boost factor from contextual cues.",
    )
    enable_caching: bool = Field(
        default=True,
        description="Cache classification results for repeated segments.",
    )
    cache_size: int = Field(
        default=1000,
        ge=1,
        description="Maximum number of cached classification entries.",
    )
