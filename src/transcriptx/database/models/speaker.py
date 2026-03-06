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
    func,
    hybrid_property,
)
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4


class Speaker(Base):
    """
    Speaker entity representing a participant in conversations.

    This model stores basic speaker information and maintains relationships
    to their profiles, behavioral fingerprints, and participation in conversations.
    """

    __tablename__ = "speakers"

    # Primary key
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = Column(String(36), unique=True, default=lambda: str(uuid4()))

    # Basic information
    name: Mapped[str] = Column(String(255), nullable=False, index=True)
    display_name: Mapped[Optional[str]] = Column(String(255))
    first_name: Mapped[Optional[str]] = Column(String(255), index=True)
    surname: Mapped[Optional[str]] = Column(String(255), index=True)
    personal_note: Mapped[Optional[str]] = Column(Text)  # For disambiguation
    email: Mapped[Optional[str]] = Column(String(255), index=True)
    organization: Mapped[Optional[str]] = Column(String(255))
    role: Mapped[Optional[str]] = Column(String(255))

    # Visual identification
    color: Mapped[Optional[str]] = Column(String(7))  # Hex color code
    avatar_url: Mapped[Optional[str]] = Column(String(500))

    # Cross-transcript tracking
    canonical_id: Mapped[Optional[str]] = Column(
        String(255), index=True
    )  # Unique identifier across sessions
    confidence_score: Mapped[Optional[float]] = Column(
        Float
    )  # Overall confidence in speaker identity
    is_verified: Mapped[bool] = Column(
        Boolean, default=False
    )  # Manually verified speaker

    # Metadata
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )
    is_active: Mapped[bool] = Column(Boolean, default=True)

    # Relationships
    profiles: Mapped[List["SpeakerProfile"]] = relationship(
        "SpeakerProfile", back_populates="speaker"
    )
    fingerprints: Mapped[List["BehavioralFingerprint"]] = relationship(
        "BehavioralFingerprint", back_populates="speaker"
    )
    sessions: Mapped[List["Session"]] = relationship(
        "Session", back_populates="speaker"
    )
    stats: Mapped[List["SpeakerStats"]] = relationship(
        "SpeakerStats", back_populates="speaker"
    )
    cluster_memberships: Mapped[List["SpeakerClusterMember"]] = relationship(
        "SpeakerClusterMember", back_populates="speaker"
    )
    session_participations: Mapped[List["SpeakerSession"]] = relationship(
        "SpeakerSession", back_populates="speaker"
    )
    pattern_evolutions: Mapped[List["PatternEvolution"]] = relationship(
        "PatternEvolution", back_populates="speaker"
    )
    anomalies: Mapped[List["BehavioralAnomaly"]] = relationship(
        "BehavioralAnomaly", back_populates="speaker"
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_speaker_name", "name"),
        Index("idx_speaker_email", "email"),
        Index("idx_speaker_active", "is_active"),
        Index("idx_speaker_canonical", "canonical_id"),
        Index("idx_speaker_confidence", "confidence_score"),
        Index("idx_speaker_first_name", "first_name"),
        Index("idx_speaker_surname", "surname"),
        Index(
            "idx_speaker_name_composite", "first_name", "surname"
        ),  # For duplicate detection
    )

    def __repr__(self) -> str:
        return f"<Speaker(id={self.id}, name='{self.name}')>"

    @hybrid_property
    def full_name(self) -> str:
        """Get the full display name or fall back to name."""
        return self.display_name or self.name


class SpeakerProfile(Base):
    """
    Speaker profile entity storing comprehensive behavioral and preference data.

    This model contains detailed speaker profiles that evolve over time,
    including behavioral patterns, preferences, and historical data.
    """

    __tablename__ = "speaker_profiles"

    # Primary key
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = Column(String(36), unique=True, default=lambda: str(uuid4()))

    # Foreign key
    speaker_id: Mapped[int] = Column(Integer, ForeignKey("speakers.id"), nullable=False)

    # Profile data
    profile_data: Mapped[Dict[str, Any]] = Column(
        JSONType, default=dict
    )  # Complete profile data
    preferences: Mapped[Dict[str, Any]] = Column(
        JSONType, default=dict
    )  # User preferences
    settings: Mapped[Dict[str, Any]] = Column(
        JSONType, default=dict
    )  # Analysis settings

    # Behavioral data
    vocabulary_patterns: Mapped[Dict[str, Any]] = Column(
        JSONType, default=dict
    )  # TF-IDF patterns
    speech_patterns: Mapped[Dict[str, Any]] = Column(
        JSONType, default=dict
    )  # Speaking patterns
    emotion_patterns: Mapped[Dict[str, Any]] = Column(
        JSONType, default=dict
    )  # Emotional patterns

    # Historical data
    session_history: Mapped[List[Dict[str, Any]]] = Column(
        JSONType, default=list
    )  # Session summaries
    analysis_history: Mapped[List[Dict[str, Any]]] = Column(
        JSONType, default=list
    )  # Analysis history

    # Metadata
    profile_version: Mapped[int] = Column(Integer, default=1)
    is_current: Mapped[bool] = Column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # Relationships
    speaker: Mapped["Speaker"] = relationship("Speaker", back_populates="profiles")

    # Indexes for performance
    __table_args__ = (
        Index("idx_profile_speaker", "speaker_id"),
        Index("idx_profile_current", "is_current"),
        Index("idx_profile_version", "profile_version"),
    )

    def __repr__(self) -> str:
        return f"<SpeakerProfile(id={self.id}, speaker_id={self.speaker_id}, version={self.profile_version})>"


class BehavioralFingerprint(Base):
    """
    Behavioral fingerprint entity storing detailed behavioral analysis data.

    This model contains comprehensive behavioral fingerprints that are used
    for speaker identification, pattern recognition, and behavioral analysis.
    """

    __tablename__ = "behavioral_fingerprints"

    # Primary key
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = Column(String(36), unique=True, default=lambda: str(uuid4()))

    # Foreign key
    speaker_id: Mapped[int] = Column(Integer, ForeignKey("speakers.id"), nullable=False)

    # Fingerprint data
    fingerprint_data: Mapped[Dict[str, Any]] = Column(
        JSONType, default=dict
    )  # Complete fingerprint

    # Specific behavioral metrics
    vocabulary_fingerprint: Mapped[Dict[str, Any]] = Column(
        JSONType, default=dict
    )  # Vocabulary patterns
    speech_rhythm: Mapped[Dict[str, Any]] = Column(
        JSONType, default=dict
    )  # Speaking rhythm patterns
    emotion_signature: Mapped[Dict[str, Any]] = Column(
        JSONType, default=dict
    )  # Emotional patterns
    interaction_style: Mapped[Dict[str, Any]] = Column(
        JSONType, default=dict
    )  # Interaction patterns

    # Statistical data
    statistical_signatures: Mapped[Dict[str, Any]] = Column(
        JSONType, default=dict
    )  # Statistical patterns
    temporal_patterns: Mapped[Dict[str, Any]] = Column(
        JSONType, default=dict
    )  # Time-based patterns

    # Metadata
    fingerprint_version: Mapped[int] = Column(Integer, default=1)
    confidence_score: Mapped[Optional[float]] = Column(Float)
    is_current: Mapped[bool] = Column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # Relationships
    speaker: Mapped["Speaker"] = relationship("Speaker", back_populates="fingerprints")

    # Indexes for performance
    __table_args__ = (
        Index("idx_fingerprint_speaker", "speaker_id"),
        Index("idx_fingerprint_current", "is_current"),
        Index("idx_fingerprint_confidence", "confidence_score"),
    )

    def __repr__(self) -> str:
        return f"<BehavioralFingerprint(id={self.id}, speaker_id={self.speaker_id}, version={self.fingerprint_version})>"


class SpeakerStats(Base):
    """
    Speaker statistics entity storing aggregated statistical data.

    This model stores comprehensive statistical data about speakers,
    including speaking patterns, performance metrics, and behavioral trends.
    """

    __tablename__ = "speaker_stats"

    # Primary key
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = Column(String(36), unique=True, default=lambda: str(uuid4()))

    # Foreign key
    speaker_id: Mapped[int] = Column(Integer, ForeignKey("speakers.id"), nullable=False)

    # Statistical data
    stats_data: Mapped[Dict[str, Any]] = Column(
        JSONType, default=dict
    )  # Complete statistics

    # Speaking metrics
    total_speaking_time: Mapped[Optional[float]] = Column(Float)
    total_word_count: Mapped[Optional[int]] = Column(Integer)
    total_segment_count: Mapped[Optional[int]] = Column(Integer)
    average_speaking_rate: Mapped[Optional[float]] = Column(Float)

    # Performance metrics
    average_sentiment_score: Mapped[Optional[float]] = Column(Float)
    dominant_emotion: Mapped[Optional[str]] = Column(String(50))
    emotion_distribution: Mapped[Dict[str, float]] = Column(JSONType, default=dict)

    # Behavioral metrics
    vocabulary_richness: Mapped[Optional[float]] = Column(Float)
    repetition_rate: Mapped[Optional[float]] = Column(Float)
    interaction_frequency: Mapped[Optional[float]] = Column(Float)

    # Metadata
    stats_period: Mapped[str] = Column(
        String(50), default="all_time"
    )  # all_time, monthly, weekly, etc.
    is_current: Mapped[bool] = Column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # Relationships
    speaker: Mapped["Speaker"] = relationship("Speaker", back_populates="stats")

    # Indexes for performance
    __table_args__ = (
        Index("idx_stats_speaker", "speaker_id"),
        Index("idx_stats_period", "stats_period"),
        Index("idx_stats_current", "is_current"),
    )

    def __repr__(self) -> str:
        return f"<SpeakerStats(id={self.id}, speaker_id={self.speaker_id}, period='{self.stats_period}')>"


class SpeakerSentimentProfile(Base):
    """
    Speaker sentiment profile entity storing comprehensive sentiment analysis data.

    This model contains detailed sentiment profiles for speakers, including
    sentiment scores, volatility, trends, and trigger words.
    """

    __tablename__ = "speaker_sentiment_profiles"

    # Primary key
    speaker_id: Mapped[int] = Column(
        Integer, ForeignKey("speakers.id"), primary_key=True
    )

    # Sentiment metrics
    average_sentiment_score: Mapped[Optional[float]] = Column(Float)
    sentiment_volatility: Mapped[Optional[float]] = Column(Float)
    dominant_sentiment_pattern: Mapped[Optional[str]] = Column(String(50))
    sentiment_trends: Mapped[Dict[str, Any]] = Column(JSONType, default=dict)
    positive_trigger_words: Mapped[List[str]] = Column(JSONType, default=list)
    negative_trigger_words: Mapped[List[str]] = Column(JSONType, default=list)
    sentiment_consistency_score: Mapped[Optional[float]] = Column(Float)

    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # Relationships
    speaker: Mapped["Speaker"] = relationship("Speaker")

    # Indexes for performance
    __table_args__ = (
        Index("idx_sentiment_profile_score", "average_sentiment_score"),
        Index("idx_sentiment_profile_volatility", "sentiment_volatility"),
        Index("idx_sentiment_profile_consistency", "sentiment_consistency_score"),
    )

    def __repr__(self) -> str:
        return f"<SpeakerSentimentProfile(speaker_id={self.speaker_id}, avg_score={self.average_sentiment_score})>"


class SpeakerEmotionProfile(Base):
    """
    Speaker emotion profile entity storing comprehensive emotion analysis data.

    This model contains detailed emotion profiles for speakers, including
    dominant emotions, distribution, stability, and transition patterns.
    """

    __tablename__ = "speaker_emotion_profiles"

    # Primary key
    speaker_id: Mapped[int] = Column(
        Integer, ForeignKey("speakers.id"), primary_key=True
    )

    # Emotion metrics
    dominant_emotion: Mapped[Optional[str]] = Column(String(50))
    emotion_distribution: Mapped[Dict[str, float]] = Column(JSONType, default=dict)
    emotional_stability: Mapped[Optional[float]] = Column(Float)
    emotion_transition_patterns: Mapped[Dict[str, Any]] = Column(JSONType, default=dict)
    emotional_reactivity: Mapped[Optional[float]] = Column(Float)
    emotion_consistency: Mapped[Optional[float]] = Column(Float)

    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # Relationships
    speaker: Mapped["Speaker"] = relationship("Speaker")

    # Indexes for performance
    __table_args__ = (
        Index("idx_emotion_profile_dominant", "dominant_emotion"),
        Index("idx_emotion_profile_stability", "emotional_stability"),
        Index("idx_emotion_profile_reactivity", "emotional_reactivity"),
        Index("idx_emotion_profile_consistency", "emotion_consistency"),
    )

    def __repr__(self) -> str:
        return f"<SpeakerEmotionProfile(speaker_id={self.speaker_id}, dominant='{self.dominant_emotion}')>"


class SpeakerTopicProfile(Base):
    """
    Speaker topic profile entity storing comprehensive topic modeling data.

    This model contains detailed topic profiles for speakers, including
    preferred topics, expertise scores, and engagement patterns.
    """

    __tablename__ = "speaker_topic_profiles"

    # Primary key
    speaker_id: Mapped[int] = Column(
        Integer, ForeignKey("speakers.id"), primary_key=True
    )

    # Topic metrics
    preferred_topics: Mapped[Dict[str, float]] = Column(JSONType, default=dict)
    topic_expertise_scores: Mapped[Dict[str, float]] = Column(JSONType, default=dict)
    topic_contribution_patterns: Mapped[Dict[str, Any]] = Column(JSONType, default=dict)
    topic_engagement_style: Mapped[Optional[str]] = Column(String(50))
    topic_evolution_trends: Mapped[Dict[str, Any]] = Column(JSONType, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # Relationships
    speaker: Mapped["Speaker"] = relationship("Speaker")

    # Indexes for performance
    __table_args__ = (Index("idx_topic_profile_engagement", "topic_engagement_style"),)

    def __repr__(self) -> str:
        return f"<SpeakerTopicProfile(speaker_id={self.speaker_id}, engagement='{self.topic_engagement_style}')>"


class SpeakerEntityProfile(Base):
    """
    Speaker entity profile entity storing comprehensive NER analysis data.

    This model contains detailed entity profiles for speakers, including
    expertise domains, frequently mentioned entities, and entity networks.
    """

    __tablename__ = "speaker_entity_profiles"

    # Primary key
    speaker_id: Mapped[int] = Column(
        Integer, ForeignKey("speakers.id"), primary_key=True
    )

    # Entity metrics
    entity_expertise_domains: Mapped[Dict[str, float]] = Column(JSONType, default=dict)
    frequently_mentioned_entities: Mapped[Dict[str, int]] = Column(
        JSONType, default=dict
    )
    entity_network: Mapped[Dict[str, Any]] = Column(JSONType, default=dict)
    entity_sentiment_patterns: Mapped[Dict[str, Any]] = Column(JSONType, default=dict)
    entity_evolution: Mapped[Dict[str, Any]] = Column(JSONType, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # Relationships
    speaker: Mapped["Speaker"] = relationship("Speaker")

    def __repr__(self) -> str:
        return f"<SpeakerEntityProfile(speaker_id={self.speaker_id})>"


class SpeakerTicProfile(Base):
    """
    Speaker tic profile entity storing comprehensive verbal tics analysis data.

    This model contains detailed tic profiles for speakers, including
    tic frequency, types, context patterns, and evolution.
    """

    __tablename__ = "speaker_tic_profiles"

    # Primary key
    speaker_id: Mapped[int] = Column(
        Integer, ForeignKey("speakers.id"), primary_key=True
    )

    # Tic metrics
    tic_frequency: Mapped[Dict[str, int]] = Column(JSONType, default=dict)
    tic_types: Mapped[Dict[str, float]] = Column(JSONType, default=dict)
    tic_context_patterns: Mapped[Dict[str, Any]] = Column(JSONType, default=dict)
    tic_evolution: Mapped[Dict[str, Any]] = Column(JSONType, default=dict)
    tic_reduction_goals: Mapped[Dict[str, Any]] = Column(JSONType, default=dict)
    tic_confidence_indicators: Mapped[Dict[str, float]] = Column(JSONType, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # Relationships
    speaker: Mapped["Speaker"] = relationship("Speaker")

    def __repr__(self) -> str:
        return f"<SpeakerTicProfile(speaker_id={self.speaker_id})>"


class SpeakerSemanticProfile(Base):
    """
    Speaker semantic profile entity storing comprehensive semantic similarity data.

    This model contains detailed semantic profiles for speakers, including
    semantic fingerprints, vocabulary sophistication, and consistency.
    """

    __tablename__ = "speaker_semantic_profiles"

    # Primary key
    speaker_id: Mapped[int] = Column(
        Integer, ForeignKey("speakers.id"), primary_key=True
    )

    # Semantic metrics
    semantic_fingerprint: Mapped[Dict[str, Any]] = Column(JSONType, default=dict)
    vocabulary_sophistication: Mapped[Optional[float]] = Column(Float)
    semantic_consistency: Mapped[Optional[float]] = Column(Float)
    agreement_patterns: Mapped[Dict[str, Any]] = Column(JSONType, default=dict)
    disagreement_patterns: Mapped[Dict[str, Any]] = Column(JSONType, default=dict)
    semantic_evolution: Mapped[Dict[str, Any]] = Column(JSONType, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # Relationships
    speaker: Mapped["Speaker"] = relationship("Speaker")

    # Indexes for performance
    __table_args__ = (
        Index("idx_semantic_profile_sophistication", "vocabulary_sophistication"),
        Index("idx_semantic_profile_consistency", "semantic_consistency"),
    )

    def __repr__(self) -> str:
        return f"<SpeakerSemanticProfile(speaker_id={self.speaker_id}, sophistication={self.vocabulary_sophistication})>"


class SpeakerInteractionProfile(Base):
    """
    Speaker interaction profile entity storing comprehensive interaction analysis data.

    This model contains detailed interaction profiles for speakers, including
    interaction styles, patterns, influence, and collaboration scores.
    """

    __tablename__ = "speaker_interaction_profiles"

    # Primary key
    speaker_id: Mapped[int] = Column(
        Integer, ForeignKey("speakers.id"), primary_key=True
    )

    # Interaction metrics
    interaction_style: Mapped[Optional[str]] = Column(String(50))
    interruption_patterns: Mapped[Dict[str, Any]] = Column(JSONType, default=dict)
    response_patterns: Mapped[Dict[str, Any]] = Column(JSONType, default=dict)
    interaction_network: Mapped[Dict[str, Any]] = Column(JSONType, default=dict)
    influence_score: Mapped[Optional[float]] = Column(Float)
    collaboration_score: Mapped[Optional[float]] = Column(Float)

    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # Relationships
    speaker: Mapped["Speaker"] = relationship("Speaker")

    # Indexes for performance
    __table_args__ = (
        Index("idx_interaction_profile_style", "interaction_style"),
        Index("idx_interaction_profile_influence", "influence_score"),
        Index("idx_interaction_profile_collaboration", "collaboration_score"),
    )

    def __repr__(self) -> str:
        return f"<SpeakerInteractionProfile(speaker_id={self.speaker_id}, style='{self.interaction_style}')>"


class SpeakerPerformanceProfile(Base):
    """
    Speaker performance profile entity storing comprehensive performance analysis data.

    This model contains detailed performance profiles for speakers, including
    speaking styles, participation patterns, and performance metrics.
    """

    __tablename__ = "speaker_performance_profiles"

    # Primary key
    speaker_id: Mapped[int] = Column(
        Integer, ForeignKey("speakers.id"), primary_key=True
    )

    # Performance metrics
    speaking_style: Mapped[Optional[str]] = Column(String(50))
    participation_patterns: Mapped[Dict[str, Any]] = Column(JSONType, default=dict)
    performance_metrics: Mapped[Dict[str, Any]] = Column(JSONType, default=dict)
    improvement_areas: Mapped[Dict[str, Any]] = Column(JSONType, default=dict)
    strengths: Mapped[Dict[str, Any]] = Column(JSONType, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # Relationships
    speaker: Mapped["Speaker"] = relationship("Speaker")

    # Indexes for performance
    __table_args__ = (Index("idx_performance_profile_style", "speaking_style"),)

    def __repr__(self) -> str:
        return f"<SpeakerPerformanceProfile(speaker_id={self.speaker_id}, style='{self.speaking_style}')>"
