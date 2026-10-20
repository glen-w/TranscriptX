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
    treat_as_single_speaker: bool = Field(
        default=False,
        description=(
            "When True, a single turn-taking speaker (e.g. import-minted SPEAKER_00) "
            "counts for modules that need at least one speaker without enabling full "
            "unnamed-speaker mode for multi-speaker meetings."
        ),
    )
