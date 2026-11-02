"""Analysis facade dataclasses for this Pydantic pilot."""

from __future__ import annotations

from dataclasses import dataclass, field

from .analysis_hydrate import _hydrate_dataclass_from_pydantic


@dataclass
class GroupLLMSynthesisConfig:
    """Defaults owned by GroupLLMSynthesisSettingsModel."""

    enabled: bool = field(init=False, repr=True)
    effort: str = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.group_llm_synthesis import (
            GroupLLMSynthesisSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, GroupLLMSynthesisSettingsModel())
