"""Pydantic schema for analysis.qa_analysis."""

from pydantic import BaseModel, Field


class QAAnalysisSettingsModel(BaseModel):
    response_time_threshold: float = Field(default=10.0)
    weight_directness: float = Field(default=0.3)
    weight_completeness: float = Field(default=0.3)
    weight_relevance: float = Field(default=0.25)
    weight_length: float = Field(default=0.15)
    min_match_threshold: float = Field(default=0.3)
    good_match_threshold: float = Field(default=0.5)
    high_match_threshold: float = Field(default=0.7)
    min_answer_length: int = Field(default=2)
    optimal_answer_length: int = Field(default=5)
    max_answer_length: int = Field(default=50)
