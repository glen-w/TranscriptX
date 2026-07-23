"""Pydantic schema for analysis.politeness."""

from pydantic import BaseModel, Field


class PolitenessSettingsModel(BaseModel):
    min_tokens_for_rates: int = Field(default=20, ge=1)
    enabled_categories: list[str] = Field(default_factory=list)
