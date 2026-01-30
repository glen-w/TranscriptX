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


class Conversation(Base):
    """
    Conversation entity representing a complete conversation or meeting.

    This model stores metadata about conversations and maintains relationships
    to sessions, analysis results, and participants.
    """

    __tablename__ = "conversations"

    # Primary key
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = Column(String(36), unique=True, default=lambda: str(uuid4()))

    # Basic information
    title: Mapped[str] = Column(String(500), nullable=False)
    description: Mapped[Optional[str]] = Column(Text)
    meeting_id: Mapped[Optional[str]] = Column(String(255), index=True)

    # File information
    audio_file_path: Mapped[Optional[str]] = Column(String(1000))
    transcript_file_path: Mapped[Optional[str]] = Column(String(1000))
    readable_transcript_path: Mapped[Optional[str]] = Column(String(1000))

    # Metadata
    duration_seconds: Mapped[Optional[float]] = Column(Float)
    word_count: Mapped[Optional[int]] = Column(Integer)
    speaker_count: Mapped[Optional[int]] = Column(Integer)

    # Analysis metadata
    analysis_status: Mapped[str] = Column(
        String(50), default="pending"
    )  # pending, in_progress, completed, failed
    analysis_config: Mapped[Dict[str, Any]] = Column(JSONType, default=dict)

    # Timestamps
    conversation_date: Mapped[Optional[datetime]] = Column(DateTime)
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # Relationships
    sessions: Mapped[List["Session"]] = relationship(
        "Session", back_populates="conversation"
    )
    analysis_results: Mapped[List["AnalysisResult"]] = relationship(
        "AnalysisResult", back_populates="conversation"
    )
    conversation_metadata: Mapped[List["ConversationMetadata"]] = relationship(
        "ConversationMetadata", back_populates="conversation"
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_conversation_title", "title"),
        Index("idx_conversation_meeting_id", "meeting_id"),
        Index("idx_conversation_date", "conversation_date"),
        Index("idx_conversation_status", "analysis_status"),
    )

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, title='{self.title}')>"


class Session(Base):
    """
    Session entity representing a speaker's participation in a conversation.

    This model tracks individual speaker sessions within conversations,
    including their speaking segments and performance metrics.
    """

    __tablename__ = "sessions"

    # Primary key
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = Column(String(36), unique=True, default=lambda: str(uuid4()))

    # Foreign keys
    speaker_id: Mapped[int] = Column(Integer, ForeignKey("speakers.id"), nullable=False)
    conversation_id: Mapped[int] = Column(
        Integer, ForeignKey("conversations.id"), nullable=False
    )

    # Session data
    segments_data: Mapped[Dict[str, Any]] = Column(
        JSONType, default=dict
    )  # Raw segment data
    speaking_time_seconds: Mapped[Optional[float]] = Column(Float)
    word_count: Mapped[Optional[int]] = Column(Integer)
    segment_count: Mapped[Optional[int]] = Column(Integer)

    # Performance metrics
    average_speaking_rate: Mapped[Optional[float]] = Column(Float)
    longest_segment_seconds: Mapped[Optional[float]] = Column(Float)
    shortest_segment_seconds: Mapped[Optional[float]] = Column(Float)

    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # Relationships
    speaker: Mapped["Speaker"] = relationship("Speaker", back_populates="sessions")
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="sessions"
    )
    speaker_participations: Mapped[List["SpeakerSession"]] = relationship(
        "SpeakerSession", back_populates="session"
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_session_speaker", "speaker_id"),
        Index("idx_session_conversation", "conversation_id"),
        UniqueConstraint(
            "speaker_id", "conversation_id", name="uq_speaker_conversation"
        ),
    )

    def __repr__(self) -> str:
        return f"<Session(id={self.id}, speaker_id={self.speaker_id}, conversation_id={self.conversation_id})>"


class ConversationMetadata(Base):
    """
    Conversation metadata entity storing additional conversation information.

    This model stores metadata about conversations that doesn't fit into
    the main conversation model, such as tags, categories, and custom fields.
    """

    __tablename__ = "conversation_metadata"

    # Primary key
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = Column(String(36), unique=True, default=lambda: str(uuid4()))

    # Foreign key
    conversation_id: Mapped[int] = Column(
        Integer, ForeignKey("conversations.id"), nullable=False
    )

    # Metadata
    key: Mapped[str] = Column(String(255), nullable=False)
    value: Mapped[str] = Column(Text)
    value_type: Mapped[str] = Column(
        String(50), default="string"
    )  # string, number, boolean, json
    category: Mapped[Optional[str]] = Column(String(100))

    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="conversation_metadata"
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_metadata_conversation", "conversation_id"),
        Index("idx_metadata_key", "key"),
        Index("idx_metadata_category", "category"),
        UniqueConstraint("conversation_id", "key", name="uq_conversation_metadata_key"),
    )

    def __repr__(self) -> str:
        return f"<ConversationMetadata(id={self.id}, conversation_id={self.conversation_id}, key='{self.key}')>"


# Additional models for specific analysis types
