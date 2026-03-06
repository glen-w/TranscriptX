"""Correction Studio database models."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .base import (
    Base,
    JSONType,
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
    UniqueConstraint,
    Index,
    func,
)


class CorrectionSession(Base):
    """Resumable correction review session tied to a transcript."""

    __tablename__ = "correction_sessions"

    id: Mapped[str] = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    transcript_file_id: Mapped[Optional[int]] = Column(
        Integer, ForeignKey("transcript_files.id"), nullable=True
    )
    transcript_path: Mapped[str] = Column(String(1000), nullable=False)
    source_fingerprint: Mapped[str] = Column(String(64), nullable=False)
    detector_version: Mapped[str] = Column(String(40), nullable=False)
    status: Mapped[str] = Column(String(20), nullable=False, default="active")
    ui_state_json: Mapped[Optional[Dict[str, Any]]] = Column(JSONType, nullable=True)

    created_at: Mapped[datetime] = Column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    candidates: Mapped[List["CorrectionCandidate"]] = relationship(
        "CorrectionCandidate", back_populates="session", cascade="all, delete"
    )
    decisions: Mapped[List["CorrectionDecision"]] = relationship(
        "CorrectionDecision", back_populates="session", cascade="all, delete"
    )

    __table_args__ = (
        Index("idx_correction_session_path_status", "transcript_path", "status"),
    )


class CorrectionCandidate(Base):
    """A detected correction candidate within a session."""

    __tablename__ = "correction_candidates"

    id: Mapped[str] = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str] = Column(
        String(36),
        ForeignKey("correction_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_hash: Mapped[str] = Column(String(40), nullable=False)
    kind: Mapped[str] = Column(String(30), nullable=False)
    wrong_text: Mapped[str] = Column(Text, nullable=False)
    suggested_text: Mapped[str] = Column(Text, nullable=False)
    confidence: Mapped[Optional[float]] = Column(Float, nullable=True)
    rule_id: Mapped[Optional[str]] = Column(String(40), nullable=True)
    occurrences_json: Mapped[Any] = Column(JSONType, nullable=False)
    evidence_json: Mapped[Optional[Any]] = Column(JSONType, nullable=True)
    status: Mapped[str] = Column(String(20), nullable=False, default="pending")

    created_at: Mapped[datetime] = Column(DateTime, default=func.now())

    session: Mapped["CorrectionSession"] = relationship(
        "CorrectionSession", back_populates="candidates"
    )

    __table_args__ = (
        Index("idx_correction_candidate_session_status", "session_id", "status"),
    )


class CorrectionDecision(Base):
    """A user decision on a correction candidate."""

    __tablename__ = "correction_decisions"

    id: Mapped[str] = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str] = Column(
        String(36),
        ForeignKey("correction_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_id: Mapped[str] = Column(
        String(36),
        ForeignKey("correction_candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    decision: Mapped[str] = Column(String(20), nullable=False)
    selected_occurrence_ids_json: Mapped[Optional[Any]] = Column(
        JSONType, nullable=True
    )
    created_rule_id: Mapped[Optional[str]] = Column(
        String(36),
        ForeignKey("correction_rules_db.id", ondelete="SET NULL"),
        nullable=True,
    )
    note: Mapped[Optional[str]] = Column(Text, nullable=True)
    actor: Mapped[str] = Column(String(50), nullable=False, default="web")

    created_at: Mapped[datetime] = Column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    session: Mapped["CorrectionSession"] = relationship(
        "CorrectionSession", back_populates="decisions"
    )

    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "candidate_id",
            name="uq_correction_decision_session_candidate",
        ),
    )


class CorrectionRuleDB(Base):
    """DB-persisted correction rule (name avoids collision with Pydantic CorrectionRule)."""

    __tablename__ = "correction_rules_db"

    id: Mapped[str] = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    rule_hash: Mapped[str] = Column(String(40), nullable=False)
    scope: Mapped[str] = Column(String(20), nullable=False)
    rule_type: Mapped[str] = Column(String(20), nullable=False)
    wrong_variants_json: Mapped[Any] = Column(JSONType, nullable=False)
    replacement_text: Mapped[str] = Column(Text, nullable=False)
    confidence: Mapped[float] = Column(Float, default=0.0)
    auto_apply: Mapped[bool] = Column(Boolean, default=False)
    conditions_json: Mapped[Optional[Any]] = Column(JSONType, nullable=True)
    is_person_name: Mapped[bool] = Column(Boolean, default=False)
    enabled: Mapped[bool] = Column(Boolean, default=True)
    source_session_id: Mapped[Optional[str]] = Column(
        String(36),
        ForeignKey("correction_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    transcript_path: Mapped[Optional[str]] = Column(String(1000), nullable=True)

    created_at: Mapped[datetime] = Column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "rule_hash",
            "scope",
            "transcript_path",
            name="uq_correction_rule_hash_scope_path",
        ),
    )
