"""Analysis facade dataclasses for this Pydantic pilot."""

from __future__ import annotations

from dataclasses import dataclass, field

from .analysis_hydrate import _hydrate_dataclass_from_pydantic


@dataclass
class TopicModelingConfig:
    """Configuration for topic modeling. Defaults owned by TopicModelingSettingsModel."""

    max_features: int = field(init=False, repr=True)
    min_df: int = field(init=False, repr=True)
    max_df: float = field(init=False, repr=True)
    ngram_range: tuple[int, int] = field(init=False, repr=True)
    random_state: int = field(init=False, repr=True)
    max_iter_lda: int = field(init=False, repr=True)
    max_iter_nmf: int = field(init=False, repr=True)
    alpha_H: float = field(init=False, repr=True)
    tol: float = field(init=False, repr=True)
    learning_method: str = field(init=False, repr=True)
    k_range: tuple[int, int] = field(init=False, repr=True)
    test_size: float = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.topic_modeling import (
            TopicModelingSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, TopicModelingSettingsModel())
