"""Analysis facade dataclasses for this Pydantic pilot."""

from __future__ import annotations

from dataclasses import dataclass, field

from .analysis_hydrate import _hydrate_dataclass_from_pydantic


@dataclass
class BERTopicConfig:
    """Configuration for BERTopic. Defaults owned by BERTopicSettingsModel."""

    embedding_model: str = field(init=False, repr=True)
    min_topic_size: int = field(init=False, repr=True)
    nr_topics: str = field(init=False, repr=True)
    top_n_words: int = field(init=False, repr=True)
    label_words: int = field(init=False, repr=True)
    calculate_probabilities: bool = field(init=False, repr=True)
    timeout_seconds: float = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.bertopic import (
            BERTopicSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, BERTopicSettingsModel())
