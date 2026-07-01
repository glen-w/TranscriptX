"""Pydantic schema for analysis.speaker_exemplars."""

from pydantic import BaseModel, Field


class SpeakerExemplarsMethodsEnabledModel(BaseModel):
    unique: bool = Field(default=True)
    tfidf_within_speaker: bool = Field(default=True)
    distinctive_vs_others: bool = Field(default=True)


class SpeakerExemplarsWeightsModel(BaseModel):
    unique: float = Field(default=0.34)
    tfidf_within_speaker: float = Field(default=0.33)
    distinctive_vs_others: float = Field(default=0.33)


class SpeakerExemplarsSettingsModel(BaseModel):
    enabled: bool = Field(default=True)
    count: int = Field(default=10)
    min_words: int = Field(default=3)
    max_words: int = Field(default=80)
    max_segments_considered: int = Field(default=2000)
    merge_adjacent: bool = Field(default=True)
    dedupe: bool = Field(default=True)
    near_dedupe: bool = Field(default=False)
    near_dedupe_threshold: float = Field(default=0.85)
    near_dedupe_max_checks: int = Field(default=200)
    methods_enabled: SpeakerExemplarsMethodsEnabledModel = Field(
        default_factory=SpeakerExemplarsMethodsEnabledModel
    )
    weights: SpeakerExemplarsWeightsModel = Field(
        default_factory=SpeakerExemplarsWeightsModel
    )
    distinctive_scope: str = Field(default="transcript")
    distinctive_min_other_segments: int = Field(default=50)
    distinctive_max_other_speakers: int = Field(default=6)
    distinctive_max_other_segments_total: int = Field(default=2000)
    distinctive_max_other_segments_per_speaker: int = Field(default=400)
    tfidf_max_features: int = Field(default=1000)
    tfidf_ngram_range: tuple[int, int] = Field(default=(1, 2))
    length_prior_enabled: bool = Field(default=True)
    length_prior_center: float = Field(default=18.0)
    length_prior_sigma: float = Field(default=12.0)
