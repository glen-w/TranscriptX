"""Pydantic schema for analysis.momentum."""

from pydantic import BaseModel, Field


class MomentumWeightsModel(BaseModel):
    pause_rate: float = Field(default=-0.3)
    repetition_rate: float = Field(default=-0.3)
    loop_rate: float = Field(default=-0.2)
    novelty: float = Field(default=0.4)
    turn_energy: float = Field(default=0.3)


class MomentumSettingsModel(BaseModel):
    window_length_seconds: float = Field(default=60.0)
    window_step_seconds: float = Field(default=30.0)
    stall_threshold_percentile: float = Field(default=0.15)
    min_stall_duration_seconds: float = Field(default=30.0)
    momentum_cliff_threshold: float = Field(default=-0.2)
    novelty_lookback_windows: int = Field(default=3)
    weights: MomentumWeightsModel = Field(default_factory=MomentumWeightsModel)
