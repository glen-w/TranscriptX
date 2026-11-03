"""Analysis facade dataclasses for this Pydantic pilot."""

from __future__ import annotations

from dataclasses import dataclass, field

from .analysis_hydrate import _hydrate_dataclass_from_pydantic


@dataclass
class ActsConfig:
    """Configuration for dialogue acts. Defaults owned by ActsSettingsModel."""

    method: str = field(init=False, repr=True)
    use_context: bool = field(init=False, repr=True)
    context_window_size: int = field(init=False, repr=True)
    context_window_type: str = field(init=False, repr=True)
    include_speaker_info: bool = field(init=False, repr=True)
    include_timing_info: bool = field(init=False, repr=True)
    min_confidence: float = field(init=False, repr=True)
    high_confidence_threshold: float = field(init=False, repr=True)
    ensemble_weight_transformer: float = field(init=False, repr=True)
    ensemble_weight_ml: float = field(init=False, repr=True)
    ensemble_weight_rules: float = field(init=False, repr=True)
    ml_model_name: str = field(init=False, repr=True)
    ml_use_gpu: bool = field(init=False, repr=True)
    ml_batch_size: int = field(init=False, repr=True)
    ml_max_length: int = field(init=False, repr=True)
    rules_use_enhanced_patterns: bool = field(init=False, repr=True)
    rules_use_fallback_logic: bool = field(init=False, repr=True)
    rules_confidence_boost_exact_match: float = field(init=False, repr=True)
    rules_context_boost_factor: float = field(init=False, repr=True)
    enable_caching: bool = field(init=False, repr=True)
    cache_size: int = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.acts import (
            ActsSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, ActsSettingsModel())
