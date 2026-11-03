"""Analysis facade dataclasses for this Pydantic pilot."""

from __future__ import annotations

from dataclasses import dataclass, field

from .analysis_hydrate import _hydrate_dataclass_from_pydantic


@dataclass
class AffectTensionConfig:
    """Configuration for affect_tension. Defaults owned by AffectTensionSettingsModel."""

    mismatch_compound_threshold: float = field(init=False, repr=True)
    trust_like_threshold: float = field(init=False, repr=True)
    pos_emotion_threshold: float = field(init=False, repr=True)
    weight_posneg_mismatch: float = field(init=False, repr=True)
    weight_trust_neutral: float = field(init=False, repr=True)
    weight_entropy: float = field(init=False, repr=True)
    weight_volatility: float = field(init=False, repr=True)
    window_segments: int = field(init=False, repr=True)
    window_seconds: float | None = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.affect_tension import (
            AffectTensionSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, AffectTensionSettingsModel())
