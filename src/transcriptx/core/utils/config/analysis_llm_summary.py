"""Analysis facade dataclasses for this Pydantic pilot."""

from __future__ import annotations

from dataclasses import dataclass, field

from .analysis_hydrate import _hydrate_dataclass_from_pydantic


@dataclass
class LLMSummaryConfig:
    """Configuration for llm_summary. Defaults owned by LLMSummarySettingsModel."""

    effort: str = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.llm_summary import LLMSummarySettingsModel

        _hydrate_dataclass_from_pydantic(self, LLMSummarySettingsModel())
