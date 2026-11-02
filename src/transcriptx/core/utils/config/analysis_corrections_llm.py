"""Analysis facade dataclasses for this Pydantic pilot."""

from __future__ import annotations

from dataclasses import dataclass, field

from .analysis_hydrate import _hydrate_dataclass_from_pydantic


@dataclass
class CorrectionsLlmConfig:
    """Nested LLM settings for Corrections Studio. Defaults from CorrectionsLlmSettingsModel."""

    enabled: bool = field(init=False, repr=True)
    effort: str = field(init=False, repr=True)
    request_timeout_seconds: float = field(init=False, repr=True)
    total_wall_clock_seconds: float = field(init=False, repr=True)
    max_chunks: int = field(init=False, repr=True)
    chunk_max_segments: int = field(init=False, repr=True)
    chunk_overlap_segments: int = field(init=False, repr=True)
    max_candidates_per_chunk: int = field(init=False, repr=True)
    max_candidates_per_transcript: int = field(init=False, repr=True)
    continue_on_failure: bool = field(init=False, repr=True)
    assess_deterministic: bool = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.corrections_llm import (
            CorrectionsLlmSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, CorrectionsLlmSettingsModel())
