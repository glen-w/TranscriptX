"""Pydantic schema for analysis.temporal_dynamics."""

from pydantic import BaseModel, Field


class TemporalDynamicsSettingsModel(BaseModel):
    window_size: float = Field(default=30.0)
    weight_segment_factor: float = Field(default=0.4)
    weight_length_factor: float = Field(default=0.3)
    weight_question_factor: float = Field(default=0.3)
    max_segments_normalization: float = Field(default=10.0)
    max_questions_normalization: float = Field(default=5.0)
    opening_phase_percentage: float = Field(default=0.1)
    opening_phase_max_seconds: float = Field(default=120.0)
    closing_phase_percentage: float = Field(default=0.1)
    closing_phase_max_seconds: float = Field(default=120.0)
    sentiment_change_threshold: float = Field(default=0.1)
    engagement_change_threshold: float = Field(default=0.05)
    speaking_rate_change_threshold: float = Field(default=10.0)
