"""Analysis facade dataclasses for this Pydantic pilot."""

from __future__ import annotations

from dataclasses import dataclass, field

from .analysis_hydrate import _hydrate_dataclass_from_pydantic


@dataclass
class TemporalDynamicsConfig:
    """Configuration for temporal dynamics. Defaults owned by TemporalDynamicsSettingsModel."""

    window_size: float = field(init=False, repr=True)
    weight_segment_factor: float = field(init=False, repr=True)
    weight_length_factor: float = field(init=False, repr=True)
    weight_question_factor: float = field(init=False, repr=True)
    max_segments_normalization: float = field(init=False, repr=True)
    max_questions_normalization: float = field(init=False, repr=True)
    opening_phase_percentage: float = field(init=False, repr=True)
    opening_phase_max_seconds: float = field(init=False, repr=True)
    closing_phase_percentage: float = field(init=False, repr=True)
    closing_phase_max_seconds: float = field(init=False, repr=True)
    sentiment_change_threshold: float = field(init=False, repr=True)
    engagement_change_threshold: float = field(init=False, repr=True)
    speaking_rate_change_threshold: float = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.temporal_dynamics import (
            TemporalDynamicsSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, TemporalDynamicsSettingsModel())
