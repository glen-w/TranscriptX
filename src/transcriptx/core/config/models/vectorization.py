"""Pydantic schema for analysis.vectorization."""

from pydantic import BaseModel, Field


class VectorizationSettingsModel(BaseModel):
    max_features: int = Field(default=1000)
    min_df: int = Field(default=1)
    max_df: float = Field(default=0.95)
    ngram_range: tuple[int, int] = Field(default=(1, 2))
    wordcloud_max_features: int = Field(default=300)
    wordcloud_ngram_range: tuple[int, int] = Field(default=(1, 2))
