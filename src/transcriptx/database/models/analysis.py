"""Database models."""

from .base import Base, JSONType
from .base import (
    Mapped,
    relationship,
    Column,
    Integer,
    String,
    Text,
    Float,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    func,
)
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4


class AnalysisResult(Base):
    """
    Analysis result entity storing the output of various analysis modules.

    This model stores results from sentiment analysis, topic modeling,
    NER analysis, and other analysis modules for each conversation.
    """

    __tablename__ = "analysis_results"

    # Primary key
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = Column(String(36), unique=True, default=lambda: str(uuid4()))

    # Foreign key
    conversation_id: Mapped[int] = Column(
        Integer, ForeignKey("conversations.id"), nullable=False
    )

    # Analysis metadata
    analysis_type: Mapped[str] = Column(
        String(100), nullable=False
    )  # sentiment, topic_modeling, ner, etc.
    analysis_version: Mapped[str] = Column(String(50), default="1.0")
    analysis_config: Mapped[Dict[str, Any]] = Column(JSONType, default=dict)

    # Results data
    results_data: Mapped[Dict[str, Any]] = Column(
        JSONType, default=dict
    )  # Complete results
    summary_data: Mapped[Dict[str, Any]] = Column(
        JSONType, default=dict
    )  # Summary statistics
    analysis_metadata: Mapped[Dict[str, Any]] = Column(
        JSONType, default=dict
    )  # Additional metadata

    # Performance metrics
    processing_time_seconds: Mapped[Optional[float]] = Column(Float)
    memory_usage_mb: Mapped[Optional[float]] = Column(Float)

    # Status
    status: Mapped[str] = Column(
        String(50), default="completed"
    )  # pending, in_progress, completed, failed
    error_message: Mapped[Optional[str]] = Column(Text)

    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="analysis_results"
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_analysis_conversation", "conversation_id"),
        Index("idx_analysis_type", "analysis_type"),
        Index("idx_analysis_status", "status"),
        UniqueConstraint(
            "conversation_id", "analysis_type", name="uq_conversation_analysis_type"
        ),
    )

    def __repr__(self) -> str:
        return f"<AnalysisResult(id={self.id}, conversation_id={self.conversation_id}, type='{self.analysis_type}')>"


class EntityMention(Base):
    """Entity mention entity storing named entity recognition results."""

    __tablename__ = "entity_mentions"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = Column(
        Integer, ForeignKey("conversations.id"), nullable=False
    )
    speaker_id: Mapped[Optional[int]] = Column(Integer, ForeignKey("speakers.id"))

    entity_text: Mapped[str] = Column(String(255), nullable=False)
    entity_type: Mapped[str] = Column(String(50), nullable=False)
    confidence_score: Mapped[Optional[float]] = Column(Float)
    mention_count: Mapped[int] = Column(Integer, default=1)

    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_entity_conversation", "conversation_id"),
        Index("idx_entity_speaker", "speaker_id"),
        Index("idx_entity_type", "entity_type"),
    )


class TopicModel(Base):
    """Topic model entity storing topic modeling results."""

    __tablename__ = "topic_models"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = Column(
        Integer, ForeignKey("conversations.id"), nullable=False
    )

    topic_id: Mapped[int] = Column(Integer, nullable=False)
    topic_words: Mapped[Dict[str, float]] = Column(JSONType, default=dict)
    topic_coherence: Mapped[Optional[float]] = Column(Float)
    topic_documents: Mapped[List[int]] = Column(JSONType, default=list)

    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())

    __table_args__ = (
        Index("idx_topic_conversation", "conversation_id"),
        Index("idx_topic_id", "topic_id"),
        UniqueConstraint("conversation_id", "topic_id", name="uq_conversation_topic"),
    )


class SentimentAnalysis(Base):
    """Sentiment analysis entity storing sentiment analysis results."""

    __tablename__ = "sentiment_analyses"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = Column(
        Integer, ForeignKey("conversations.id"), nullable=False
    )
    speaker_id: Mapped[Optional[int]] = Column(Integer, ForeignKey("speakers.id"))

    segment_id: Mapped[Optional[int]] = Column(Integer)
    sentiment_score: Mapped[float] = Column(Float, nullable=False)
    sentiment_label: Mapped[str] = Column(String(50), nullable=False)
    confidence_score: Mapped[Optional[float]] = Column(Float)

    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())

    __table_args__ = (
        Index("idx_sentiment_conversation", "conversation_id"),
        Index("idx_sentiment_speaker", "speaker_id"),
        Index("idx_sentiment_score", "sentiment_score"),
    )


class EmotionAnalysis(Base):
    """Emotion analysis entity storing emotion analysis results."""

    __tablename__ = "emotion_analyses"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = Column(
        Integer, ForeignKey("conversations.id"), nullable=False
    )
    speaker_id: Mapped[Optional[int]] = Column(Integer, ForeignKey("speakers.id"))

    segment_id: Mapped[Optional[int]] = Column(Integer)
    emotion_scores: Mapped[Dict[str, float]] = Column(JSONType, default=dict)
    dominant_emotion: Mapped[str] = Column(String(50), nullable=False)
    confidence_score: Mapped[Optional[float]] = Column(Float)

    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())

    __table_args__ = (
        Index("idx_emotion_conversation", "conversation_id"),
        Index("idx_emotion_speaker", "speaker_id"),
        Index("idx_emotion_dominant", "dominant_emotion"),
    )


class InteractionPattern(Base):
    """Interaction pattern entity storing speaker interaction analysis."""

    __tablename__ = "interaction_patterns"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = Column(
        Integer, ForeignKey("conversations.id"), nullable=False
    )

    speaker_id: Mapped[int] = Column(Integer, ForeignKey("speakers.id"), nullable=False)
    target_speaker_id: Mapped[int] = Column(
        Integer, ForeignKey("speakers.id"), nullable=False
    )

    interaction_type: Mapped[str] = Column(
        String(50), nullable=False
    )  # interruption, response, overlap, etc.
    interaction_count: Mapped[int] = Column(Integer, default=1)
    total_duration: Mapped[Optional[float]] = Column(Float)

    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())

    __table_args__ = (
        Index("idx_interaction_conversation", "conversation_id"),
        Index("idx_interaction_speaker", "speaker_id"),
        Index("idx_interaction_target", "target_speaker_id"),
        Index("idx_interaction_type", "interaction_type"),
    )
