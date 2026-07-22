"""Pydantic schema for analysis.transcript_quality."""

from pydantic import BaseModel, Field


class TranscriptQualitySettingsModel(BaseModel):
    low_score_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    max_gap_seconds: float = Field(default=0.75, ge=0.0)
    cluster_merge_seconds: float = Field(default=2.0, ge=0.0)
    max_spans: int = Field(default=50, ge=1)
    max_clusters: int = Field(default=25, ge=1)
