"""Analysis facade dataclasses for this Pydantic pilot."""

from __future__ import annotations

from dataclasses import dataclass, field

from .analysis_hydrate import _hydrate_dataclass_from_pydantic


@dataclass
class EmotionLexicalConfig:
    """analysis.emotion.* lexical settings."""

    low_coverage_threshold: float = field(init=False, repr=True)
    no_hit_rate_warn: float = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.analysis_emotion_family import (
            EmotionLexicalSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, EmotionLexicalSettingsModel())


@dataclass
class ContextualEmotionConfig:
    """analysis.contextual_emotion.* experimental classifier settings."""

    profile_id: str = field(init=False, repr=True)
    confidence_threshold: float = field(init=False, repr=True)
    batch_size: int = field(init=False, repr=True)
    release_channel: str = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.analysis_emotion_family import (
            ContextualEmotionSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, ContextualEmotionSettingsModel())


@dataclass
class FineGrainedEmotionConfig:
    """analysis.fine_grained_emotion.* experimental multilabel settings."""

    profile_id: str = field(init=False, repr=True)
    label_threshold: float = field(init=False, repr=True)
    max_labels_per_segment: int = field(init=False, repr=True)
    batch_size: int = field(init=False, repr=True)
    release_channel: str = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.analysis_emotion_family import (
            FineGrainedEmotionSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, FineGrainedEmotionSettingsModel())
