"""Pydantic schema for analysis.corrections.llm."""

from pydantic import BaseModel, Field


class CorrectionsLlmSettingsModel(BaseModel):
    enabled: bool = Field(default=False)
    effort: str = Field(default="low")
    request_timeout_seconds: float = Field(default=120.0)
    total_wall_clock_seconds: float = Field(default=180.0)
    max_chunks: int = Field(default=25)
    chunk_max_segments: int = Field(default=40)
    chunk_overlap_segments: int = Field(default=4)
    max_candidates_per_chunk: int = Field(default=10)
    max_candidates_per_transcript: int = Field(default=80)
    continue_on_failure: bool = Field(default=True)
    assess_deterministic: bool = Field(default=False)
