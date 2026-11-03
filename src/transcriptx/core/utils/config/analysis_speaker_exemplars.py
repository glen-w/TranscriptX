"""Analysis facade dataclasses for this Pydantic pilot."""

from __future__ import annotations

from dataclasses import dataclass, field

from .analysis_hydrate import _hydrate_dataclass_from_pydantic


@dataclass
class SpeakerExemplarsConfig:
    """Configuration for speaker exemplars. Defaults owned by SpeakerExemplarsSettingsModel."""

    enabled: bool = field(init=False, repr=True)
    count: int = field(init=False, repr=True)
    min_words: int = field(init=False, repr=True)
    max_words: int = field(init=False, repr=True)
    max_segments_considered: int = field(init=False, repr=True)
    merge_adjacent: bool = field(init=False, repr=True)
    dedupe: bool = field(init=False, repr=True)
    near_dedupe: bool = field(init=False, repr=True)
    near_dedupe_threshold: float = field(init=False, repr=True)
    near_dedupe_max_checks: int = field(init=False, repr=True)
    methods_enabled: dict[str, bool] = field(init=False, repr=True)
    weights: dict[str, float] = field(init=False, repr=True)
    distinctive_scope: str = field(init=False, repr=True)
    distinctive_min_other_segments: int = field(init=False, repr=True)
    distinctive_max_other_speakers: int = field(init=False, repr=True)
    distinctive_max_other_segments_total: int = field(init=False, repr=True)
    distinctive_max_other_segments_per_speaker: int = field(init=False, repr=True)
    tfidf_max_features: int = field(init=False, repr=True)
    tfidf_ngram_range: tuple[int, int] = field(init=False, repr=True)
    length_prior_enabled: bool = field(init=False, repr=True)
    length_prior_center: float = field(init=False, repr=True)
    length_prior_sigma: float = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.speaker_exemplars import (
            SpeakerExemplarsSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, SpeakerExemplarsSettingsModel())
