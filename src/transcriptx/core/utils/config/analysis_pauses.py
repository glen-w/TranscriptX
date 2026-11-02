"""Analysis facade dataclasses for this Pydantic pilot."""

from __future__ import annotations

from dataclasses import dataclass, field

from .analysis_hydrate import _hydrate_dataclass_from_pydantic


@dataclass
class PausesConfig:
    """Configuration for pauses analysis. Defaults owned by PausesSettingsModel."""

    min_long_pause_seconds: float = field(init=False, repr=True)
    post_question_multiplier: float = field(init=False, repr=True)
    percentile_long_pause: float = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.pauses import PausesSettingsModel

        _hydrate_dataclass_from_pydantic(self, PausesSettingsModel())
