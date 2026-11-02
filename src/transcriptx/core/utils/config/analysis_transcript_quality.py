"""Analysis facade dataclasses for this Pydantic pilot."""

from __future__ import annotations

from dataclasses import dataclass, field

from .analysis_hydrate import _hydrate_dataclass_from_pydantic


@dataclass
class TranscriptQualityConfig:
    """ASR confidence settings. Defaults owned by TranscriptQualitySettingsModel."""

    low_score_threshold: float = field(init=False, repr=True)
    max_gap_seconds: float = field(init=False, repr=True)
    cluster_merge_seconds: float = field(init=False, repr=True)
    max_spans: int = field(init=False, repr=True)
    max_clusters: int = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.transcript_quality import (
            TranscriptQualitySettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, TranscriptQualitySettingsModel())
