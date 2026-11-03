"""Analysis facade dataclasses for this Pydantic pilot."""

from __future__ import annotations

from dataclasses import dataclass, field

from .analysis_hydrate import _hydrate_dataclass_from_pydantic


@dataclass
class InsightsCounts:
    top_themes: int = field(init=False, repr=True)
    top_recurring_ideas: int = field(init=False, repr=True)
    top_notable_moments: int = field(init=False, repr=True)
    overview_theme_cap: int = field(init=False, repr=True)


@dataclass
class InsightsConfig:
    """Insights composer settings. Defaults owned by InsightsSettingsModel."""

    enabled: bool = field(init=False, repr=True)
    counts: InsightsCounts = field(init=False, repr=True)
    min_theme_score: float = field(init=False, repr=True)
    min_themes_for_signal: int = field(init=False, repr=True)
    topic_boost: float = field(init=False, repr=True)
    narrative_enabled: bool = field(init=False, repr=True)
    narrative_min_evidence_quotes: int = field(init=False, repr=True)
    narrative_max_chars: int = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.insights import InsightsSettingsModel

        _hydrate_dataclass_from_pydantic(self, InsightsSettingsModel())
