"""Analysis facade dataclasses for this Pydantic pilot."""

from __future__ import annotations

from dataclasses import dataclass, field

from .analysis_hydrate import _hydrate_dataclass_from_pydantic


@dataclass
class NamesConfig:
    """Names module settings. Defaults owned by AnalysisNamesSettingsModel."""

    min_mentions: int = field(init=False, repr=True)
    exclude_known_speakers: bool = field(init=False, repr=True)
    max_mentions_per_person: int = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.analysis_names import (
            AnalysisNamesSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, AnalysisNamesSettingsModel())
