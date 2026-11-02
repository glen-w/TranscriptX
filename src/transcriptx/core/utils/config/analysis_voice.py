"""Analysis facade dataclasses for this Pydantic pilot."""

from __future__ import annotations

from dataclasses import dataclass, field

from .analysis_hydrate import _hydrate_dataclass_from_pydantic


@dataclass
class VoiceConfig:
    """Configuration for voice modality analysis (CPU-first).

    Defaults owned by VoiceSettingsModel.
    """

    enabled: bool = field(init=False, repr=True)
    sample_rate: int = field(init=False, repr=True)
    vad_mode: int = field(init=False, repr=True)
    pad_s: float = field(init=False, repr=True)
    max_seconds_for_pitch: float = field(init=False, repr=True)
    max_segments_considered: int | None = field(init=False, repr=True)
    egemaps_enabled: bool = field(init=False, repr=True)
    deep_mode: bool = field(init=False, repr=True)
    deep_model_name: str = field(init=False, repr=True)
    deep_max_seconds: float = field(init=False, repr=True)
    store_parquet: str = field(init=False, repr=True)
    strict_audio_hash: bool = field(init=False, repr=True)
    mismatch_threshold: float = field(init=False, repr=True)
    top_k_moments: int = field(init=False, repr=True)
    drift_threshold: float = field(init=False, repr=True)
    bin_seconds: float = field(init=False, repr=True)
    smoothing_alpha: float = field(init=False, repr=True)
    include_unnamed_in_global_curves: bool = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.voice import VoiceSettingsModel

        _hydrate_dataclass_from_pydantic(self, VoiceSettingsModel())
