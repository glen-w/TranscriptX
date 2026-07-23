"""Pydantic schema for analysis.epistemic_markers."""

from pydantic import BaseModel, Field


class EpistemicMarkersSettingsModel(BaseModel):
    min_tokens_for_rates: int = Field(default=20, ge=1)
    enabled_categories: list[str] = Field(default_factory=list)
