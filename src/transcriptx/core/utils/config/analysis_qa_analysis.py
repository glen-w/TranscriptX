"""Analysis facade dataclasses for this Pydantic pilot."""

from __future__ import annotations

from dataclasses import dataclass, field

from .analysis_hydrate import _hydrate_dataclass_from_pydantic


@dataclass
class QAAnalysisConfig:
    """Configuration for Q&A analysis. Defaults owned by QAAnalysisSettingsModel."""

    response_time_threshold: float = field(init=False, repr=True)
    weight_directness: float = field(init=False, repr=True)
    weight_completeness: float = field(init=False, repr=True)
    weight_relevance: float = field(init=False, repr=True)
    weight_length: float = field(init=False, repr=True)
    min_match_threshold: float = field(init=False, repr=True)
    good_match_threshold: float = field(init=False, repr=True)
    high_match_threshold: float = field(init=False, repr=True)
    min_answer_length: int = field(init=False, repr=True)
    optimal_answer_length: int = field(init=False, repr=True)
    max_answer_length: int = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.qa_analysis import (
            QAAnalysisSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, QAAnalysisSettingsModel())
