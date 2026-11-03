"""Analysis facade dataclasses for this Pydantic pilot."""

from __future__ import annotations

from dataclasses import dataclass, field

from .analysis_hydrate import _hydrate_dataclass_from_pydantic


@dataclass
class HighlightsCounts:
    cold_open_quotes: int = field(init=False, repr=True)
    total_highlights: int = field(init=False, repr=True)
    conflict_windows: int = field(init=False, repr=True)
    emblematic_phrases: int = field(init=False, repr=True)


@dataclass
class HighlightsThresholds:
    conflict_spike_percentile: float = field(init=False, repr=True)
    min_gap_seconds: float = field(init=False, repr=True)
    min_quote_words: int = field(init=False, repr=True)
    min_quote_chars: int = field(init=False, repr=True)
    max_quote_words: int = field(init=False, repr=True)
    max_consecutive_per_speaker: int = field(init=False, repr=True)
    min_phrase_len: int = field(init=False, repr=True)
    max_phrase_len: int = field(init=False, repr=True)
    min_phrase_frequency: int = field(init=False, repr=True)


@dataclass
class HighlightsWeights:
    intensity: float = field(init=False, repr=True)
    conflict: float = field(init=False, repr=True)
    uniqueness: float = field(init=False, repr=True)
    keyword_richness: float = field(init=False, repr=True)
    content_density: float = field(init=False, repr=True)


@dataclass
class HighlightsSections:
    cold_open_enabled: bool = field(init=False, repr=True)
    conflict_points_enabled: bool = field(init=False, repr=True)
    emblematic_phrases_enabled: bool = field(init=False, repr=True)


@dataclass
class HighlightsOutput:
    write_conflict_csv: bool = field(init=False, repr=True)


@dataclass
class HighlightsMergeAdjacent:
    enabled: bool = field(init=False, repr=True)
    max_gap_seconds: float = field(init=False, repr=True)
    max_segments: int = field(init=False, repr=True)


@dataclass
class HighlightsConflict:
    window_seconds: float = field(init=False, repr=True)
    step_seconds: float = field(init=False, repr=True)
    merge_gap_seconds: float = field(init=False, repr=True)


@dataclass
class HighlightsColdOpen:
    window_seconds: float = field(init=False, repr=True)
    window_policy: str = field(init=False, repr=True)


@dataclass
class HighlightsConfig:
    """Configuration for highlights. Defaults owned by HighlightsSettingsModel."""

    enabled: bool = field(init=False, repr=True)
    counts: HighlightsCounts = field(init=False, repr=True)
    thresholds: HighlightsThresholds = field(init=False, repr=True)
    weights: HighlightsWeights = field(init=False, repr=True)
    sections: HighlightsSections = field(init=False, repr=True)
    output: HighlightsOutput = field(init=False, repr=True)
    merge_adjacent: HighlightsMergeAdjacent = field(init=False, repr=True)
    conflict: HighlightsConflict = field(init=False, repr=True)
    cold_open: HighlightsColdOpen = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.highlights import HighlightsSettingsModel

        _hydrate_dataclass_from_pydantic(self, HighlightsSettingsModel())
