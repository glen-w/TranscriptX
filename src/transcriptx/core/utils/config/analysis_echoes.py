"""Analysis facade dataclasses for this Pydantic pilot."""

from __future__ import annotations

from dataclasses import dataclass, field

from .analysis_hydrate import _hydrate_dataclass_from_pydantic


@dataclass
class EchoesConfig:
    """Configuration for echoes. Defaults owned by EchoesSettingsModel."""

    lookback_seconds: float = field(init=False, repr=True)
    max_candidates: int = field(init=False, repr=True)
    explicit_quote_weight: float = field(init=False, repr=True)
    lexical_echo_threshold: float = field(init=False, repr=True)
    paraphrase_threshold: float = field(init=False, repr=True)
    min_tokens: int = field(init=False, repr=True)
    exclude_phrases: list[str] = field(init=False, repr=True)
    enable_semantic_paraphrase: bool = field(init=False, repr=True)
    semantic_model_name: str | None = field(init=False, repr=True)
    echo_burst_window_seconds: float = field(init=False, repr=True)
    echo_burst_min_events: int = field(init=False, repr=True)
    echo_burst_percentile_threshold: float = field(init=False, repr=True)

    def __post_init__(self) -> None:
        from transcriptx.core.config.models.echoes import (
            EchoesSettingsModel,
        )

        _hydrate_dataclass_from_pydantic(self, EchoesSettingsModel())
