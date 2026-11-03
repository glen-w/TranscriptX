"""Analysis facade dataclasses for this Pydantic pilot."""

from __future__ import annotations

from dataclasses import dataclass, field

from .analysis_hydrate import _hydrate_dataclass_from_pydantic


@dataclass
class SummaryCounts:
    theme_bullets: int = field(init=False, repr=True)
    tension_bullets: int = field(init=False, repr=True)
    commitments: int = field(init=False, repr=True)


@dataclass
class SummarySections:
    overview_enabled: bool = field(init=False, repr=True)
    key_themes_enabled: bool = field(init=False, repr=True)
    tension_points_enabled: bool = field(init=False, repr=True)
    commitments_enabled: bool = field(init=False, repr=True)


@dataclass
class SummaryCommitments:
    rules: list[str] = field(init=False, repr=True)
    max_per_owner: int = field(init=False, repr=True)


@dataclass
class SummaryConfig:
    """Configuration for summary. Defaults owned by SummarySettingsModel."""

    enabled: bool = field(init=False, repr=True)
    require_highlights: bool = field(init=False, repr=True)
    compute_highlights_if_missing: bool = field(init=False, repr=True)
    allow_degraded: bool = field(init=False, repr=True)
    counts: SummaryCounts = field(init=False, repr=True)
    sections: SummarySections = field(init=False, repr=True)
    commitments: SummaryCommitments = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.summary import SummarySettingsModel

        _hydrate_dataclass_from_pydantic(self, SummarySettingsModel())
