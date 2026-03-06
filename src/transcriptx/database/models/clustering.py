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


class SpeakerCluster(Base):
    """
    Speaker cluster entity for grouping similar speakers.

    This model allows grouping speakers based on behavioral similarities,
    organizational relationships, or other criteria.
    """

    __tablename__ = "speaker_clusters"

    # Primary key
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = Column(String(36), unique=True, default=lambda: str(uuid4()))

    # Basic information
    name: Mapped[str] = Column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = Column(Text)
    cluster_type: Mapped[str] = Column(
        String(50), default="behavioral"
    )  # behavioral, organizational, manual

    # Cluster metadata
    member_count: Mapped[int] = Column(Integer, default=0)
    average_confidence: Mapped[Optional[float]] = Column(Float)
    cluster_coherence: Mapped[Optional[float]] = Column(
        Float
    )  # How similar cluster members are

    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # Relationships
    members: Mapped[List["SpeakerClusterMember"]] = relationship(
        "SpeakerClusterMember", back_populates="cluster"
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_cluster_name", "name"),
        Index("idx_cluster_type", "cluster_type"),
        Index("idx_cluster_coherence", "cluster_coherence"),
    )

    def __repr__(self) -> str:
        return f"<SpeakerCluster(id={self.id}, name='{self.name}')>"


class SpeakerClusterMember(Base):
    """
    Speaker cluster membership entity.

    This model tracks which speakers belong to which clusters,
    along with confidence scores and membership metadata.
    """

    __tablename__ = "speaker_cluster_members"

    # Primary key
    speaker_id: Mapped[int] = Column(
        Integer, ForeignKey("speakers.id"), primary_key=True
    )
    cluster_id: Mapped[int] = Column(
        Integer, ForeignKey("speaker_clusters.id"), primary_key=True
    )

    # Membership data
    confidence_score: Mapped[float] = Column(Float, nullable=False)
    membership_type: Mapped[str] = Column(
        String(50), default="automatic"
    )  # automatic, manual, suggested

    # Timestamps
    joined_at: Mapped[datetime] = Column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # Relationships
    speaker: Mapped["Speaker"] = relationship(
        "Speaker", back_populates="cluster_memberships"
    )
    cluster: Mapped["SpeakerCluster"] = relationship(
        "SpeakerCluster", back_populates="members"
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_cluster_member_speaker", "speaker_id"),
        Index("idx_cluster_member_cluster", "cluster_id"),
        Index("idx_cluster_member_confidence", "confidence_score"),
    )

    def __repr__(self) -> str:
        return f"<SpeakerClusterMember(speaker_id={self.speaker_id}, cluster_id={self.cluster_id})>"


class SpeakerLink(Base):
    """
    Cross-session speaker link entity.

    This model tracks links between speakers across different sessions,
    supporting speaker identification and tracking across conversations.
    """

    __tablename__ = "speaker_links"

    # Primary key
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = Column(String(36), unique=True, default=lambda: str(uuid4()))

    # Foreign keys
    source_speaker_id: Mapped[int] = Column(
        Integer, ForeignKey("speakers.id"), nullable=False
    )
    target_speaker_id: Mapped[int] = Column(
        Integer, ForeignKey("speakers.id"), nullable=False
    )

    # Link data
    confidence_score: Mapped[float] = Column(Float, nullable=False)
    link_type: Mapped[str] = Column(
        String(50), nullable=False
    )  # exact_match, fuzzy_match, manual_link, suggested
    evidence_data: Mapped[Dict[str, Any]] = Column(
        JSONType, default=dict
    )  # Supporting evidence for the link

    # Link metadata
    is_active: Mapped[bool] = Column(Boolean, default=True)
    verification_status: Mapped[str] = Column(
        String(50), default="pending"
    )  # pending, verified, rejected

    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # Relationships
    source_speaker: Mapped["Speaker"] = relationship(
        "Speaker", foreign_keys=[source_speaker_id]
    )
    target_speaker: Mapped["Speaker"] = relationship(
        "Speaker", foreign_keys=[target_speaker_id]
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_speaker_link_source", "source_speaker_id"),
        Index("idx_speaker_link_target", "target_speaker_id"),
        Index("idx_speaker_link_confidence", "confidence_score"),
        Index("idx_speaker_link_type", "link_type"),
        Index("idx_speaker_link_status", "verification_status"),
        UniqueConstraint(
            "source_speaker_id", "target_speaker_id", name="uq_speaker_link"
        ),
    )

    def __repr__(self) -> str:
        return f"<SpeakerLink(id={self.id}, source={self.source_speaker_id}, target={self.target_speaker_id})>"


class SpeakerSession(Base):
    """
    Speaker session participation entity.

    This model tracks detailed information about speaker participation
    in specific sessions, including behavioral consistency and patterns.
    """

    __tablename__ = "speaker_sessions"

    # Primary key
    speaker_id: Mapped[int] = Column(
        Integer, ForeignKey("speakers.id"), primary_key=True
    )
    session_id: Mapped[int] = Column(
        Integer, ForeignKey("sessions.id"), primary_key=True
    )

    # Participation data
    participation_score: Mapped[float] = Column(
        Float, nullable=False
    )  # How actively the speaker participated
    behavioral_consistency: Mapped[float] = Column(
        Float
    )  # How consistent behavior was with historical patterns
    speaking_time_ratio: Mapped[Optional[float]] = Column(
        Float
    )  # Percentage of total session time spent speaking
    interaction_frequency: Mapped[Optional[float]] = Column(
        Float
    )  # Frequency of interactions with other speakers

    # Session metadata
    first_seen: Mapped[datetime] = Column(DateTime, nullable=False)
    last_seen: Mapped[datetime] = Column(DateTime, nullable=False)
    total_segments: Mapped[int] = Column(Integer, default=0)
    total_words: Mapped[int] = Column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # Relationships
    speaker: Mapped["Speaker"] = relationship(
        "Speaker", back_populates="session_participations"
    )
    session: Mapped["Session"] = relationship(
        "Session", back_populates="speaker_participations"
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_speaker_session_speaker", "speaker_id"),
        Index("idx_speaker_session_session", "session_id"),
        Index("idx_speaker_session_consistency", "behavioral_consistency"),
        Index("idx_speaker_session_participation", "participation_score"),
    )

    def __repr__(self) -> str:
        return f"<SpeakerSession(speaker_id={self.speaker_id}, session_id={self.session_id})>"


class PatternEvolution(Base):
    """
    Pattern evolution tracking entity.

    This model tracks how speaker behavioral patterns change over time,
    providing insights into speaker development and adaptation.
    """

    __tablename__ = "pattern_evolution"

    # Primary key
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = Column(String(36), unique=True, default=lambda: str(uuid4()))

    # Foreign key
    speaker_id: Mapped[int] = Column(Integer, ForeignKey("speakers.id"), nullable=False)

    # Evolution data
    pattern_type: Mapped[str] = Column(
        String(50), nullable=False
    )  # vocabulary, speech_rhythm, emotion, interaction
    old_value: Mapped[Dict[str, Any]] = Column(
        JSONType, default=dict
    )  # Previous pattern state
    new_value: Mapped[Dict[str, Any]] = Column(
        JSONType, default=dict
    )  # New pattern state
    change_confidence: Mapped[float] = Column(
        Float, nullable=False
    )  # Confidence in the detected change
    change_magnitude: Mapped[float] = Column(Float)  # How significant the change is

    # Evolution metadata
    change_reason: Mapped[Optional[str]] = Column(String(255))  # Reason for the change
    is_significant: Mapped[bool] = Column(
        Boolean, default=False
    )  # Whether this is a significant change

    # Timestamps
    detected_at: Mapped[datetime] = Column(DateTime, default=func.now())
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())

    # Relationships
    speaker: Mapped["Speaker"] = relationship(
        "Speaker", back_populates="pattern_evolutions"
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_pattern_evolution_speaker", "speaker_id"),
        Index("idx_pattern_evolution_type", "pattern_type"),
        Index("idx_pattern_evolution_confidence", "change_confidence"),
        Index("idx_pattern_evolution_detected", "detected_at"),
    )

    def __repr__(self) -> str:
        return f"<PatternEvolution(id={self.id}, speaker_id={self.speaker_id}, pattern_type='{self.pattern_type}')>"


class BehavioralAnomaly(Base):
    """
    Behavioral anomaly entity.

    This model tracks unusual behavioral patterns detected in speakers,
    helping identify potential issues or interesting behavioral changes.
    """

    __tablename__ = "behavioral_anomalies"

    # Primary key
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = Column(String(36), unique=True, default=lambda: str(uuid4()))

    # Foreign keys
    speaker_id: Mapped[int] = Column(Integer, ForeignKey("speakers.id"), nullable=False)
    session_id: Mapped[Optional[int]] = Column(Integer, ForeignKey("sessions.id"))

    # Anomaly data
    anomaly_type: Mapped[str] = Column(
        String(50), nullable=False
    )  # unusual_speech_rate, vocabulary_change, emotion_shift
    severity: Mapped[float] = Column(
        Float, nullable=False
    )  # How severe the anomaly is (0-1)
    description: Mapped[str] = Column(
        Text, nullable=False
    )  # Description of the anomaly
    evidence_data: Mapped[Dict[str, Any]] = Column(
        JSONType, default=dict
    )  # Supporting evidence

    # Anomaly metadata
    is_resolved: Mapped[bool] = Column(
        Boolean, default=False
    )  # Whether the anomaly has been resolved
    resolution_notes: Mapped[Optional[str]] = Column(
        Text
    )  # Notes about how it was resolved

    # Timestamps
    detected_at: Mapped[datetime] = Column(DateTime, default=func.now())
    resolved_at: Mapped[Optional[datetime]] = Column(DateTime)
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())

    # Relationships
    speaker: Mapped["Speaker"] = relationship("Speaker", back_populates="anomalies")
    session: Mapped[Optional["Session"]] = relationship("Session")

    # Indexes for performance
    __table_args__ = (
        Index("idx_anomaly_speaker", "speaker_id"),
        Index("idx_anomaly_session", "session_id"),
        Index("idx_anomaly_type", "anomaly_type"),
        Index("idx_anomaly_severity", "severity"),
        Index("idx_anomaly_resolved", "is_resolved"),
        Index("idx_anomaly_detected", "detected_at"),
    )

    def __repr__(self) -> str:
        return f"<BehavioralAnomaly(id={self.id}, speaker_id={self.speaker_id}, type='{self.anomaly_type}')>"


# New Speaker Profile Tables
