"""Pydantic schema for analysis.analysis_wordcloud settings."""

from __future__ import annotations


from pydantic import BaseModel, Field


class AnalysisWordcloudSettingsModel(BaseModel):
    """Partial analysis.* scalar fields for analysis_wordcloud."""

    wordcloud_max_words: int = Field(default=100)
    wordcloud_min_font_size: int = Field(default=8)
    wordcloud_stopwords: list[str] = Field(
        default_factory=lambda: [
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "can",
            "this",
            "that",
            "these",
            "those",
        ]
    )
    exclude_unidentified_from_speaker_charts: bool = Field(default=True)
    readability_metrics: list[str] = Field(
        default_factory=lambda: [
            "flesch_reading_ease",
            "flesch_kincaid_grade",
            "gunning_fog",
        ]
    )
