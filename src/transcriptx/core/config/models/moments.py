"""Pydantic schema for analysis.moments."""

from pydantic import BaseModel, Field


class MomentsWeightMapModel(BaseModel):
    long_pause: float = Field(default=0.3)
    post_question_silence: float = Field(default=0.5)
    momentum_cliff: float = Field(default=0.4)
    echo_burst: float = Field(default=0.3)
    stall_zone: float = Field(default=0.35)
    emotion_switch: float = Field(default=0.4)
    unanswered_question: float = Field(default=0.5)


class MomentsSettingsModel(BaseModel):
    top_n: int = Field(default=20)
    merge_seconds: float = Field(default=20.0)
    weight_map: MomentsWeightMapModel = Field(default_factory=MomentsWeightMapModel)
    diversity_bonus: float = Field(default=0.2)
    multi_speaker_bonus: float = Field(default=0.15)
    write_markdown: bool = Field(default=False)
    excerpt_max_chars: int = Field(default=200)
    excerpt_max_segments: int = Field(default=2)
    max_span_seconds: float = Field(default=120.0)
