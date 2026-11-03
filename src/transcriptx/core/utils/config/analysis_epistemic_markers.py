"""Analysis facade dataclasses for this Pydantic pilot."""

from __future__ import annotations

from dataclasses import dataclass, field

from .analysis_hydrate import _hydrate_dataclass_from_pydantic


@dataclass
class EpistemicMarkersConfig:
    """Epistemic marker settings. Defaults owned by EpistemicMarkersSettingsModel."""

    min_tokens_for_rates: int = field(init=False, repr=True)
    enabled_categories: list = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.epistemic_markers import (
            EpistemicMarkersSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, EpistemicMarkersSettingsModel())
