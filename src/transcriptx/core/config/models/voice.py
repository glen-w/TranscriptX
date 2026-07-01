"""Pydantic schema for analysis.voice."""

from pydantic import BaseModel, Field


class VoiceSettingsModel(BaseModel):
    enabled: bool = Field(default=True)
    sample_rate: int = Field(default=16000)
    vad_mode: int = Field(default=2)
    pad_s: float = Field(default=0.15)
    max_seconds_for_pitch: float = Field(default=20.0)
    max_segments_considered: int | None = Field(default=None)
    egemaps_enabled: bool = Field(default=True)
    deep_mode: bool = Field(default=False)
    deep_model_name: str = Field(default="superb/wav2vec2-base-superb-er")
    deep_max_seconds: float = Field(default=12.0)
    store_parquet: str = Field(default="auto")
    strict_audio_hash: bool = Field(default=False)
    mismatch_threshold: float = Field(default=0.6)
    top_k_moments: int = Field(default=30)
    drift_threshold: float = Field(default=2.5)
    bin_seconds: float = Field(default=30.0)
    smoothing_alpha: float = Field(default=0.25)
    include_unnamed_in_global_curves: bool = Field(default=True)
