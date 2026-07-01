"""Pydantic schema for analysis.analysis_interaction settings."""

from __future__ import annotations


from pydantic import BaseModel, Field


class AnalysisInteractionSettingsModel(BaseModel):
    """Partial analysis.* scalar fields for analysis_interaction."""

    interaction_overlap_threshold: float = Field(default=0.5)
    interaction_min_gap: float = Field(default=0.1)
    interaction_min_segment_length: float = Field(default=0.5)
    interaction_response_threshold: float = Field(default=2.0)
    interaction_include_responses: bool = Field(default=True)
    interaction_include_overlaps: bool = Field(default=True)
    interaction_min_interactions: int = Field(default=2)
    interaction_time_window: float = Field(default=30.0)
    loop_max_intermediate_turns: int = Field(default=2)
    loop_exclude_monologues: bool = Field(default=True)
    loop_min_gap: float = Field(default=0.1)
    loop_max_gap: float = Field(default=10.0)
