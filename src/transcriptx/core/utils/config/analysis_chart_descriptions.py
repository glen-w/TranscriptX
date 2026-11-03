"""Analysis facade dataclasses for this Pydantic pilot."""

from __future__ import annotations

from dataclasses import dataclass, field

from .analysis_hydrate import _hydrate_dataclass_from_pydantic


@dataclass
class ChartDescriptionsConfig:
    """Defaults owned by ChartDescriptionsSettingsModel."""

    enabled: bool = field(init=False, repr=True)
    chart_set: str = field(init=False, repr=True)
    max_description_chars: int = field(init=False, repr=True)
    request_timeout: float = field(init=False, repr=True)
    max_retries: int = field(init=False, repr=True)
    circuit_breaker_failures: int = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.chart_descriptions import (
            ChartDescriptionsSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, ChartDescriptionsSettingsModel())
