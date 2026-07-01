"""Pydantic schema for analysis.echoes."""

from pydantic import BaseModel, Field


class EchoesSettingsModel(BaseModel):
    lookback_seconds: float = Field(default=240.0)
    max_candidates: int = Field(default=50)
    explicit_quote_weight: float = Field(default=1.0)
    lexical_echo_threshold: float = Field(default=0.6)
    paraphrase_threshold: float = Field(default=0.75)
    min_tokens: int = Field(default=5)
    exclude_phrases: list[str] = Field(
        default_factory=lambda: ["yeah", "exactly", "right"]
    )
    enable_semantic_paraphrase: bool = Field(default=False)
    semantic_model_name: str | None = Field(default=None)
    echo_burst_window_seconds: float = Field(default=25.0)
    echo_burst_min_events: int = Field(default=3)
    echo_burst_percentile_threshold: float = Field(default=0.95)
