"""Analysis facade dataclasses for this Pydantic pilot."""

from __future__ import annotations

from dataclasses import dataclass, field

from .analysis_hydrate import _hydrate_dataclass_from_pydantic


@dataclass
class InsightEligibilityConfig:
    """Insight eligibility thresholds. Defaults owned by InsightEligibilitySettingsModel."""

    min_score: float = field(init=False, repr=True)
    min_frequency: int = field(init=False, repr=True)
    require_spread_or_recurrence_for_singletons: bool = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.insight_eligibility import (
            InsightEligibilitySettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, InsightEligibilitySettingsModel())
