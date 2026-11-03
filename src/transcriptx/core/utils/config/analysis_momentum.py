"""Analysis facade dataclasses for this Pydantic pilot."""

from __future__ import annotations

from dataclasses import dataclass, field

from .analysis_hydrate import _hydrate_dataclass_from_pydantic


@dataclass
class MomentumConfig:
    """Configuration for momentum. Defaults owned by MomentumSettingsModel."""

    window_length_seconds: float = field(init=False, repr=True)
    window_step_seconds: float = field(init=False, repr=True)
    stall_threshold_percentile: float = field(init=False, repr=True)
    min_stall_duration_seconds: float = field(init=False, repr=True)
    momentum_cliff_threshold: float = field(init=False, repr=True)
    novelty_lookback_windows: int = field(init=False, repr=True)
    weights: dict[str, float] = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.momentum import (
            MomentumSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, MomentumSettingsModel())
