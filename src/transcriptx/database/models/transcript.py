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
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    func,
)
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4


class TranscriptFile(Base):
    """
    Transcript file entity storing metadata about transcript files.

    This model stores information about each transcript file, including
    file paths, metadata, and relationships to segments.
    """

    __tablename__ = "transcript_files"

    # Primary key
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = Column(String(36), unique=True, default=lambda: str(uuid4()))

    # File information
    file_path: Mapped[str] = Column(
        String(1000), nullable=False, index=True
    )  # Full path to transcript JSON file
    file_name: Mapped[str] = Column(
        String(500), nullable=False, index=True
    )  # Base filename
    audio_file_path: Mapped[Optional[str]] = Column(
        String(1000)
    )  # Original audio file path
    source_uri: Mapped[Optional[str]] = Column(
        String(1000)
    )  # Source URI/path metadata (not identity)
    import_timestamp: Mapped[Optional[datetime]] = Column(DateTime)

    # Transcript metadata
    duration_seconds: Mapped[Optional[float]] = Column(Float)
    segment_count: Mapped[int] = Column(Integer, default=0)
    speaker_count: Mapped[int] = Column(Integer, default=0)

    # Canonical identity
    transcript_content_hash: Mapped[Optional[str]] = Column(String(64), index=True)
    schema_version: Mapped[Optional[str]] = Column(String(50), index=True)
    sentence_schema_version: Mapped[Optional[str]] = Column(String(50), index=True)
    source_hash: Mapped[Optional[str]] = Column(String(64), index=True)

    # Additional metadata
    file_metadata: Mapped[Dict[str, Any]] = Column(JSONType, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # Relationships
    segments: Mapped[List["TranscriptSegment"]] = relationship(
        "TranscriptSegment",
        back_populates="transcript_file",
        cascade="all, delete-orphan",
    )
    transcript_speakers: Mapped[List["TranscriptSpeaker"]] = relationship(
        "TranscriptSpeaker",
        back_populates="transcript_file",
        cascade="all, delete-orphan",
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_transcript_file_path", "file_path"),
        Index("idx_transcript_file_name", "file_name"),
        UniqueConstraint(
            "transcript_content_hash",
            "schema_version",
            name="uq_transcript_content_schema",
        ),
    )

    def __repr__(self) -> str:
        return f"<TranscriptFile(id={self.id}, file_name='{self.file_name}')>"


class TranscriptSpeaker(Base):
    """
    Transcript-scoped speaker entity with diarization labels.
    """

    __tablename__ = "transcript_speakers"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    transcript_file_id: Mapped[int] = Column(
        Integer,
        ForeignKey("transcript_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    speaker_label: Mapped[str] = Column(String(255), nullable=False, index=True)
    speaker_order: Mapped[Optional[int]] = Column(Integer)
    display_name: Mapped[Optional[str]] = Column(String(255))
    speaker_fingerprint: Mapped[Optional[str]] = Column(String(255))

    created_at: Mapped[datetime] = Column(DateTime, default=func.now())

    transcript_file: Mapped["TranscriptFile"] = relationship(
        "TranscriptFile", back_populates="transcript_speakers"
    )
    segments: Mapped[List["TranscriptSegment"]] = relationship(
        "TranscriptSegment", back_populates="transcript_speaker"
    )
    sentences: Mapped[List["TranscriptSentence"]] = relationship(
        "TranscriptSentence", back_populates="transcript_speaker"
    )

    __table_args__ = (
        UniqueConstraint(
            "transcript_file_id", "speaker_label", name="uq_transcript_speaker_label"
        ),
        Index("idx_transcript_speaker_file", "transcript_file_id"),
    )

    def __repr__(self) -> str:
        return f"<TranscriptSpeaker(id={self.id}, label='{self.speaker_label}')>"


class TranscriptSegment(Base):
    """
    Transcript segment entity storing individual line-level segments.

    This model stores each segment (line) from a transcript with
    speaker reference, timestamps, and text content.
    """

    __tablename__ = "transcript_segments"

    # Primary key
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = Column(String(36), unique=True, default=lambda: str(uuid4()))

    # Foreign keys
    transcript_file_id: Mapped[int] = Column(
        Integer,
        ForeignKey("transcript_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    speaker_id: Mapped[Optional[int]] = Column(
        Integer,
        ForeignKey("speakers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    transcript_speaker_id: Mapped[Optional[int]] = Column(
        Integer,
        ForeignKey("transcript_speakers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Segment data
    segment_index: Mapped[int] = Column(
        Integer, nullable=False
    )  # Order of segment in transcript (0-based)
    text: Mapped[str] = Column(Text, nullable=False)  # Segment text content
    start_time: Mapped[float] = Column(
        Float, nullable=False
    )  # Start timestamp in seconds
    end_time: Mapped[float] = Column(Float, nullable=False)  # End timestamp in seconds
    duration: Mapped[float] = Column(
        Float
    )  # Calculated duration (end_time - start_time)
    word_count: Mapped[int] = Column(Integer, default=0)  # Number of words in segment

    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # Relationships
    transcript_file: Mapped["TranscriptFile"] = relationship(
        "TranscriptFile", back_populates="segments"
    )
    speaker: Mapped[Optional["Speaker"]] = relationship(
        "Speaker", backref="transcript_segments"
    )
    transcript_speaker: Mapped[Optional["TranscriptSpeaker"]] = relationship(
        "TranscriptSpeaker", back_populates="segments"
    )
    sentences: Mapped[List["TranscriptSentence"]] = relationship(
        "TranscriptSentence",
        back_populates="transcript_segment",
        cascade="all, delete-orphan",
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_segment_file", "transcript_file_id"),
        Index("idx_segment_speaker", "speaker_id"),
        Index("idx_segment_transcript_speaker", "transcript_speaker_id"),
        Index(
            "idx_segment_time", "transcript_file_id", "start_time"
        ),  # For time-based queries
        Index(
            "idx_segment_index", "transcript_file_id", "segment_index"
        ),  # For order queries
    )

    def __repr__(self) -> str:
        return f"<TranscriptSegment(id={self.id}, file_id={self.transcript_file_id}, index={self.segment_index})>"


class TranscriptSentence(Base):
    """
    Sentence-level transcript storage with speaker_id and timestamps.

    This model stores individual sentences extracted from transcript segments,
    providing granular text units for analysis while maintaining speaker identity
    and temporal information.
    """

    __tablename__ = "transcript_sentences"

    # Primary key
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = Column(String(36), unique=True, default=lambda: str(uuid4()))

    # Foreign keys
    transcript_segment_id: Mapped[int] = Column(
        Integer,
        ForeignKey("transcript_segments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    speaker_id: Mapped[Optional[int]] = Column(
        Integer,
        ForeignKey("speakers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    transcript_speaker_id: Mapped[Optional[int]] = Column(
        Integer,
        ForeignKey("transcript_speakers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Sentence data
    sentence_index: Mapped[int] = Column(
        Integer, nullable=False
    )  # Order within segment
    text: Mapped[str] = Column(Text, nullable=False)  # Sentence text content
    start_time: Mapped[float] = Column(
        Float, nullable=False
    )  # Start timestamp in seconds
    end_time: Mapped[float] = Column(Float, nullable=False)  # End timestamp in seconds
    word_count: Mapped[int] = Column(Integer, default=0)  # Number of words in sentence
    timestamp_estimated: Mapped[bool] = Column(
        Boolean, default=True
    )  # True if interpolated, False if from word-level timestamps

    # Provenance & version
    split_method: Mapped[str] = Column(
        String(50), default="punctuation"
    )  # punctuation, nltk, spacy, whisperx_alignment
    provenance_version: Mapped[int] = Column(
        Integer, default=1
    )  # Version of splitting algorithm
    analysis_run_id: Mapped[Optional[str]] = Column(
        String(36), index=True
    )  # UUID linking sentence to analysis run (optional, future-facing)

    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())

    # Relationships
    transcript_segment: Mapped["TranscriptSegment"] = relationship(
        "TranscriptSegment", back_populates="sentences"
    )
    speaker: Mapped[Optional["Speaker"]] = relationship(
        "Speaker", backref="transcript_sentences"
    )
    transcript_speaker: Mapped[Optional["TranscriptSpeaker"]] = relationship(
        "TranscriptSpeaker", back_populates="sentences"
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_sentence_segment", "transcript_segment_id"),
        Index("idx_sentence_speaker", "speaker_id"),
        Index("idx_sentence_transcript_speaker", "transcript_speaker_id"),
        Index("idx_sentence_time", "transcript_segment_id", "start_time"),
    )

    def __repr__(self) -> str:
        return f"<TranscriptSentence(id={self.id}, segment_id={self.transcript_segment_id}, index={self.sentence_index})>"
