"""Pydantic schema for analysis.affect_tension."""

from pydantic import BaseModel, Field


class AffectTensionSettingsModel(BaseModel):
    mismatch_compound_threshold: float = Field(default=-0.1)
    trust_like_threshold: float = Field(default=0.3)
    pos_emotion_threshold: float = Field(default=0.3)
    weight_posneg_mismatch: float = Field(default=0.4)
    weight_trust_neutral: float = Field(default=0.3)
    weight_entropy: float = Field(default=0.15)
    weight_volatility: float = Field(default=0.15)
    window_segments: int = Field(default=5)
    window_seconds: float | None = Field(default=None)
