"""Pydantic schema for analysis.topic_shift."""

from pydantic import BaseModel, Field, field_validator


class TopicShiftSettingsModel(BaseModel):
    window_size: int = Field(default=5, ge=1)
    stride: int = Field(default=2, ge=1)
    smooth_width: int = Field(default=3, ge=1)
    edge_exclude: int = Field(default=1, ge=0)
    min_windows_for_detection: int = Field(default=4, ge=2)
    min_gap_windows: int = Field(default=2, ge=0)
    min_gap_seconds: float = Field(default=30.0, ge=0.0)
    max_shifts: int = Field(default=20, ge=1)
    centroid_radius: int = Field(default=2, ge=1)
    centroid_threshold: float = Field(default=0.08, ge=0.0)
    min_text_chars: int = Field(default=8, ge=1)
    max_windows_per_chunk: int = Field(default=200, ge=8)
    chunk_overlap_windows: int = Field(default=20, ge=0)
    min_duration_for_rate_seconds: float = Field(default=120.0, ge=0.0)
    en_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    multi_model: str = Field(
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    batch_size: int = Field(default=32, ge=1)
    lru_size: int = Field(default=4096, ge=0)
    timeout_seconds: float = Field(default=600.0, ge=1.0)
    k_mad: float = Field(default=3.0, ge=0.0)
    absolute_floor: float = Field(default=0.15, ge=0.0)
    min_prominence: float = Field(default=0.05, ge=0.0)
    llm_effort: str = Field(default="balanced")

    @field_validator("smooth_width")
    @classmethod
    def _odd_smooth(cls, v: int) -> int:
        if int(v) % 2 == 0:
            raise ValueError("smooth_width must be odd")
        return int(v)
