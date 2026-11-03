"""Analysis facade dataclasses for this Pydantic pilot."""

from __future__ import annotations

from dataclasses import dataclass, field

from .analysis_hydrate import _hydrate_dataclass_from_pydantic


@dataclass
class VectorizationConfig:
    """Shared vectorization config. Defaults owned by VectorizationSettingsModel."""

    max_features: int = field(init=False, repr=True)
    min_df: int = field(init=False, repr=True)
    max_df: float = field(init=False, repr=True)
    ngram_range: tuple[int, int] = field(init=False, repr=True)
    wordcloud_max_features: int = field(init=False, repr=True)
    wordcloud_ngram_range: tuple[int, int] = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.vectorization import (
            VectorizationSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, VectorizationSettingsModel())
