"""Pydantic schema for analysis.summary."""

from pydantic import BaseModel, Field


class SummaryCommitmentsModel(BaseModel):
    rules: list[str] = Field(
        default_factory=lambda: [
            "\\b(I|we)\\s+(will|can|shall|need to|have to)\\s+.+",
            "\\b(let's|lets)\\s+.+",
            "\\b(action item|to-do|next step)\\b.+",
        ]
    )
    max_per_owner: int = Field(default=3)


class SummaryCountsModel(BaseModel):
    theme_bullets: int = Field(default=6)
    tension_bullets: int = Field(default=5)
    commitments: int = Field(default=8)


class SummarySectionsModel(BaseModel):
    overview_enabled: bool = Field(default=True)
    key_themes_enabled: bool = Field(default=True)
    tension_points_enabled: bool = Field(default=True)
    commitments_enabled: bool = Field(default=True)


class SummarySettingsModel(BaseModel):
    enabled: bool = Field(default=True)
    require_highlights: bool = Field(default=False)
    compute_highlights_if_missing: bool = Field(default=True)
    allow_degraded: bool = Field(default=False)
    counts: SummaryCountsModel = Field(default_factory=SummaryCountsModel)
    sections: SummarySectionsModel = Field(default_factory=SummarySectionsModel)
    commitments: SummaryCommitmentsModel = Field(
        default_factory=SummaryCommitmentsModel
    )
