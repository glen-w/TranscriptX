"""Pydantic schema for analysis.bertopic."""

from pydantic import BaseModel, Field


class BERTopicSettingsModel(BaseModel):
    embedding_model: str = Field(default="all-MiniLM-L6-v2")
    min_topic_size: int = Field(default=5)
    nr_topics: str = Field(default="auto")
    top_n_words: int = Field(default=10)
    label_words: int = Field(default=3)
    calculate_probabilities: bool = Field(default=False)
