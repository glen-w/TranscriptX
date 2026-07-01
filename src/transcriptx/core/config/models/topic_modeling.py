"""Pydantic schema for analysis.topic_modeling."""

from pydantic import BaseModel, Field


class TopicModelingSettingsModel(BaseModel):
    max_features: int = Field(default=1000)
    min_df: int = Field(default=2)
    max_df: float = Field(default=0.95)
    ngram_range: tuple[int, int] = Field(default=(1, 2))
    random_state: int = Field(default=42)
    max_iter_lda: int = Field(default=50)
    max_iter_nmf: int = Field(default=10000)
    alpha_H: float = Field(default=0.1)
    tol: float = Field(default=0.01)
    learning_method: str = Field(default="batch")
    k_range: tuple[int, int] = Field(default=(3, 15))
    test_size: float = Field(default=0.2)
