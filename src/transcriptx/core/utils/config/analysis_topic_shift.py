"""Analysis facade dataclasses for this Pydantic pilot."""

from __future__ import annotations

from dataclasses import dataclass, field

from .analysis_hydrate import _hydrate_dataclass_from_pydantic


@dataclass
class TopicShiftConfig:
    """Topic-shift settings. Defaults owned by TopicShiftSettingsModel."""

    window_size: int = field(init=False, repr=True)
    stride: int = field(init=False, repr=True)
    smooth_width: int = field(init=False, repr=True)
    edge_exclude: int = field(init=False, repr=True)
    min_windows_for_detection: int = field(init=False, repr=True)
    min_gap_windows: int = field(init=False, repr=True)
    min_gap_seconds: float = field(init=False, repr=True)
    max_shifts: int = field(init=False, repr=True)
    centroid_radius: int = field(init=False, repr=True)
    centroid_threshold: float = field(init=False, repr=True)
    min_text_chars: int = field(init=False, repr=True)
    max_windows_per_chunk: int = field(init=False, repr=True)
    chunk_overlap_windows: int = field(init=False, repr=True)
    min_duration_for_rate_seconds: float = field(init=False, repr=True)
    en_model: str = field(init=False, repr=True)
    multi_model: str = field(init=False, repr=True)
    batch_size: int = field(init=False, repr=True)
    lru_size: int = field(init=False, repr=True)
    timeout_seconds: float = field(init=False, repr=True)
    k_mad: float = field(init=False, repr=True)
    absolute_floor: float = field(init=False, repr=True)
    min_prominence: float = field(init=False, repr=True)
    llm_effort: str = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.topic_shift import TopicShiftSettingsModel

        _hydrate_dataclass_from_pydantic(self, TopicShiftSettingsModel())
