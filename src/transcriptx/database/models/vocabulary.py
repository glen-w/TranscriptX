"""Database models."""

from .base import Base, JSONType
from .base import (
    Mapped,
    relationship,
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    func,
)
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4


class SpeakerVocabularyWord(Base):
    """
    TF-IDF vocabulary words with speaker_id for speaker identification.

    This model stores vocabulary words (including unigrams, bigrams, trigrams) with
    TF-IDF scores for each speaker, enabling queryable speaker identification based
    on linguistic patterns.

    Note: Future refactoring consideration: SpeakerVocabularyEntry may be a more
    conceptually accurate name (since entries can be words, bigrams, or trigrams),
    but SpeakerVocabularyWord is acceptable for MVP.
    """

    __tablename__ = "speaker_vocabulary_words"

    # Primary key
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = Column(String(36), unique=True, default=lambda: str(uuid4()))

    # Foreign key
    speaker_id: Mapped[int] = Column(
        Integer,
        ForeignKey("speakers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Vocabulary data
    word: Mapped[str] = Column(
        String(255), nullable=False, index=True
    )  # Word, bigram, or trigram
    tfidf_score: Mapped[float] = Column(Float, nullable=False)  # TF-IDF score
    term_frequency: Mapped[int] = Column(Integer, default=0)  # Term frequency
    document_frequency: Mapped[int] = Column(Integer, default=0)  # Document frequency

    # Metadata
    ngram_type: Mapped[str] = Column(
        String(20), default="unigram"
    )  # unigram, bigram, trigram
    source_transcript_file_id: Mapped[Optional[int]] = Column(
        Integer, ForeignKey("transcript_files.id", ondelete="SET NULL")
    )

    # Provenance & version (for snapshot semantics)
    vectorizer_params_hash: Mapped[str] = Column(
        String(64), nullable=False, index=True
    )  # Hash of TfidfVectorizer params
    source_window: Mapped[Optional[str]] = Column(
        String(50)
    )  # e.g., "full_transcript", "last_10_segments"
    snapshot_version: Mapped[int] = Column(
        Integer, default=1
    )  # Snapshot version for this speaker+transcript
    analysis_run_id: Mapped[Optional[str]] = Column(
        String(36), index=True
    )  # UUID linking vocabulary to analysis run (future-facing)

    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # Relationships
    speaker: Mapped["Speaker"] = relationship("Speaker", backref="vocabulary_words")
    transcript_file: Mapped[Optional["TranscriptFile"]] = relationship("TranscriptFile")

    # Indexes for performance
    __table_args__ = (
        Index("idx_vocab_speaker_word", "speaker_id", "word"),
        Index("idx_vocab_word", "word"),
        Index("idx_vocab_tfidf", "tfidf_score"),
        Index(
            "idx_vocab_snapshot",
            "speaker_id",
            "source_transcript_file_id",
            "snapshot_version",
        ),
        Index("idx_vocab_analysis_run", "analysis_run_id"),
        UniqueConstraint(
            "speaker_id",
            "word",
            "ngram_type",
            "source_transcript_file_id",
            "snapshot_version",
            name="uq_speaker_word_ngram_snapshot",
        ),
    )

    def __repr__(self) -> str:
        return f"<SpeakerVocabularyWord(id={self.id}, speaker_id={self.speaker_id}, word='{self.word}')>"


class SpeakerResolutionEvent(Base):
    """
    Schema-backed log of speaker identity resolution events.

    This model provides a complete audit trail of all speaker identity resolution
    decisions, enabling reproducibility, debugging, and future UI features like
    "show me unresolved speakers".

    **CRITICAL INVARIANT**: No analysis module may create, modify, or infer speaker identity.
    All speaker identity decisions must pass through SpeakerIdentityService and be logged
    as resolution events in this table.
    """

    __tablename__ = "speaker_resolution_events"

    # Primary key
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)

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
    )  # NULL if unresolved

    # Resolution data
    diarized_label: Mapped[str] = Column(String(255), nullable=False, index=True)
    method: Mapped[str] = Column(
        String(50), nullable=False
    )  # vocabulary_match, canonical_id, behavioral_fingerprint, new_speaker
    confidence: Mapped[float] = Column(Float, nullable=False)
    evidence_json: Mapped[Dict[str, Any]] = Column(
        JSONType, default=dict
    )  # Evidence, top_terms, etc.
    analysis_run_id: Mapped[Optional[str]] = Column(
        String(36), index=True
    )  # UUID linking resolution to analysis run (future-facing)

    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime, default=func.now(), index=True)

    # Relationships
    transcript_file: Mapped["TranscriptFile"] = relationship(
        "TranscriptFile", backref="resolution_events"
    )
    speaker: Mapped[Optional["Speaker"]] = relationship(
        "Speaker", backref="resolution_events"
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_resolution_event_file", "transcript_file_id"),
        Index("idx_resolution_event_speaker", "speaker_id"),
        Index("idx_resolution_event_method", "method"),
        Index(
            "idx_resolution_event_unresolved", "transcript_file_id", "speaker_id"
        ),  # For finding unresolved speakers
        Index("idx_resolution_event_analysis_run", "analysis_run_id"),
    )

    def __repr__(self) -> str:
        return f"<SpeakerResolutionEvent(id={self.id}, file_id={self.transcript_file_id}, diarized_label='{self.diarized_label}')>"


# File Tracking Models
