"""Analysis facade dataclasses for this Pydantic pilot."""

from __future__ import annotations

from dataclasses import dataclass, field

from .analysis_hydrate import _hydrate_dataclass_from_pydantic


@dataclass
class LLMActionItemsConfig:
    """Defaults owned by LLMActionItemsSettingsModel."""

    effort: str = field(init=False, repr=True)
    coerce_v1_artifacts: bool = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.llm_action_items import (
            LLMActionItemsSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, LLMActionItemsSettingsModel())
