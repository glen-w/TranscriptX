"""Pydantic schema for analysis.highlights."""

from pydantic import BaseModel, Field


class HighlightsColdOpenModel(BaseModel):
    window_seconds: float = Field(default=90.0)
    window_policy: str = Field(default="seconds")


class HighlightsConflictModel(BaseModel):
    window_seconds: float = Field(default=30.0)
    step_seconds: float = Field(default=10.0)
    merge_gap_seconds: float = Field(default=10.0)


class HighlightsCountsModel(BaseModel):
    cold_open_quotes: int = Field(default=5)
    total_highlights: int = Field(default=15)
    conflict_windows: int = Field(default=6)
    emblematic_phrases: int = Field(default=12)


class HighlightsMergeAdjacentModel(BaseModel):
    enabled: bool = Field(default=True)
    max_gap_seconds: float = Field(default=1.0)
    max_segments: int = Field(default=3)


class HighlightsOutputModel(BaseModel):
    write_conflict_csv: bool = Field(default=False)


class HighlightsSectionsModel(BaseModel):
    cold_open_enabled: bool = Field(default=True)
    conflict_points_enabled: bool = Field(default=True)
    emblematic_phrases_enabled: bool = Field(default=True)


class HighlightsThresholdsModel(BaseModel):
    conflict_spike_percentile: float = Field(default=95.0)
    min_gap_seconds: float = Field(default=30.0)
    min_quote_words: int = Field(default=4)
    min_quote_chars: int = Field(default=24)
    max_quote_words: int = Field(default=60)
    max_consecutive_per_speaker: int = Field(default=2)
    min_phrase_len: int = Field(default=2)
    max_phrase_len: int = Field(default=5)
    min_phrase_frequency: int = Field(default=3)


class HighlightsWeightsModel(BaseModel):
    intensity: float = Field(default=0.4)
    conflict: float = Field(default=0.3)
    uniqueness: float = Field(default=0.2)
    keyword_richness: float = Field(default=0.1)
    content_density: float = Field(default=0.15)


class HighlightsSettingsModel(BaseModel):
    enabled: bool = Field(default=True)
    counts: HighlightsCountsModel = Field(default_factory=HighlightsCountsModel)
    thresholds: HighlightsThresholdsModel = Field(
        default_factory=HighlightsThresholdsModel
    )
    weights: HighlightsWeightsModel = Field(default_factory=HighlightsWeightsModel)
    sections: HighlightsSectionsModel = Field(default_factory=HighlightsSectionsModel)
    output: HighlightsOutputModel = Field(default_factory=HighlightsOutputModel)
    merge_adjacent: HighlightsMergeAdjacentModel = Field(
        default_factory=HighlightsMergeAdjacentModel
    )
    conflict: HighlightsConflictModel = Field(default_factory=HighlightsConflictModel)
    cold_open: HighlightsColdOpenModel = Field(default_factory=HighlightsColdOpenModel)
