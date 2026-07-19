"""Pydantic schema for analysis.bertopic."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

_ADVANCED = {"advanced": True}


class BERTopicSettingsModel(BaseModel):
    """Canonical field definitions for BERTopic module configuration."""

    embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description=(
            "Sentence-transformers embedding model id (short name or Hub path). "
            "Default is fast and English-tuned; upgrade to all-mpnet-base-v2 for "
            "higher quality at higher cost."
        ),
    )
    min_topic_size: int = Field(
        default=5,
        ge=2,
        description=(
            "Minimum number of documents (segments) required to form a topic. "
            "Lower values yield more, finer topics; higher values merge small clusters."
        ),
        json_schema_extra=_ADVANCED,
    )
    nr_topics: str = Field(
        default="auto",
        description=(
            "Topic-count policy: `auto` lets BERTopic reduce topics after fit, "
            "or a positive integer string (e.g. `12`) to target that many topics."
        ),
        json_schema_extra=_ADVANCED,
    )
    top_n_words: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of representative words retained per topic representation.",
        json_schema_extra=_ADVANCED,
    )
    label_words: int = Field(
        default=3,
        ge=1,
        le=20,
        description=(
            "How many top words are joined into the human-readable topic label "
            "(must be ≤ top_n_words in practice)."
        ),
        json_schema_extra=_ADVANCED,
    )
    calculate_probabilities: bool = Field(
        default=False,
        description=(
            "When true, BERTopic computes soft topic probabilities per document "
            "(slower / more memory). Default false keeps hard assignments only."
        ),
        json_schema_extra=_ADVANCED,
    )

    @field_validator("nr_topics")
    @classmethod
    def _validate_nr_topics(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("nr_topics must be 'auto' or a positive integer string")
        if normalized.lower() == "auto":
            return "auto"
        if normalized.isdigit() and int(normalized) >= 1:
            return normalized
        raise ValueError("nr_topics must be 'auto' or a positive integer string")

    @field_validator("embedding_model")
    @classmethod
    def _validate_embedding_model(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("embedding_model must be a non-empty model id")
        return normalized
