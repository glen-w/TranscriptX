"""Pydantic schema for analysis speaker-gating settings."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AnalysisSpeakersSettingsModel(BaseModel):
    """Partial analysis.* scalar fields for speaker eligibility / gating."""

    allow_unnamed_speakers: bool = Field(
        default=False,
        description=(
            "When True, analysis modules treat diarized labels (SPEAKER_00, …) "
            "as eligible speakers instead of skipping until human names exist."
        ),
    )
