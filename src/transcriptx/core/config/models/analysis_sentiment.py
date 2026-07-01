"""Pydantic schema for analysis.analysis_sentiment settings."""

from __future__ import annotations


from pydantic import BaseModel, Field


class AnalysisSentimentSettingsModel(BaseModel):
    """Partial analysis.* scalar fields for analysis_sentiment."""

    sentiment_window_size: int = Field(default=10)
    sentiment_min_confidence: float = Field(default=0.1)
    emotion_min_confidence: float = Field(default=0.3)
    emotion_model_name: str = Field(
        default="bhadresh-savani/distilbert-base-uncased-emotion"
    )
    emotion_output_mode: str = Field(default="top1")
    emotion_score_threshold: float = Field(default=0.3)
    sentiment_backend: str = Field(default="vader")
    sentiment_model_name: str = Field(
        default="cardiffnlp/twitter-roberta-base-sentiment-latest"
    )
