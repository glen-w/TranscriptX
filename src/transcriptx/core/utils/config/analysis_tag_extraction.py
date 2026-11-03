"""Analysis facade dataclasses for this Pydantic pilot."""

from __future__ import annotations

from dataclasses import dataclass, field

from .analysis_hydrate import _hydrate_dataclass_from_pydantic


@dataclass
class TagExtractionConfig:
    """Configuration for tag extraction. Defaults owned by TagExtractionSettingsModel."""

    early_window_seconds: int = field(init=False, repr=True)
    early_segments: int = field(init=False, repr=True)
    min_confidence: float = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.tag_extraction import (
            TagExtractionSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, TagExtractionSettingsModel())
