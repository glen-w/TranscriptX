"""Analysis facade dataclasses for this Pydantic pilot."""

from __future__ import annotations

from dataclasses import dataclass, field

from .analysis_hydrate import _hydrate_dataclass_from_pydantic


@dataclass
class MomentsConfig:
    """Configuration for moments. Defaults owned by MomentsSettingsModel."""

    top_n: int = field(init=False, repr=True)
    merge_seconds: float = field(init=False, repr=True)
    weight_map: dict[str, float] = field(init=False, repr=True)
    diversity_bonus: float = field(init=False, repr=True)
    multi_speaker_bonus: float = field(init=False, repr=True)
    write_markdown: bool = field(init=False, repr=True)
    excerpt_max_chars: int = field(init=False, repr=True)
    excerpt_max_segments: int = field(init=False, repr=True)
    max_span_seconds: float = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.moments import (
            MomentsSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, MomentsSettingsModel())
