"""TranscriptSet database models."""

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
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
    func,
)


class TranscriptSet(Base):
    """Persisted TranscriptSet definition (optional persistence)."""

    __tablename__ = "transcript_sets"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = Column(String(36), unique=True, default=lambda: str(uuid4()))

    name: Mapped[Optional[str]] = Column(String(500), nullable=True, index=True)
    transcript_ids: Mapped[List[str]] = Column(JSONType, default=list)
    # Metadata (renamed from 'metadata' to avoid SQLAlchemy reserved name conflict)
    set_metadata: Mapped[Dict[str, Any]] = Column(JSONType, default=dict)

    created_at: Mapped[datetime] = Column(DateTime, default=func.now())

    members: Mapped[List["TranscriptSetMember"]] = relationship(
        "TranscriptSetMember", back_populates="transcript_set", cascade="all, delete"
    )

    __table_args__ = (
        Index("idx_transcript_set_name", "name"),
        Index("idx_transcript_set_created_at", "created_at"),
    )


class TranscriptSetMember(Base):
    """Ordered membership for a TranscriptSet."""

    __tablename__ = "transcript_set_members"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    set_id: Mapped[int] = Column(
        Integer,
        ForeignKey("transcript_sets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    transcript_file_id: Mapped[int] = Column(
        Integer,
        ForeignKey("transcript_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_index: Mapped[int] = Column(Integer, nullable=False)

    created_at: Mapped[datetime] = Column(DateTime, default=func.now())

    transcript_set: Mapped["TranscriptSet"] = relationship(
        "TranscriptSet", back_populates="members"
    )
    transcript_file: Mapped[Any] = relationship("TranscriptFile")

    __table_args__ = (
        UniqueConstraint(
            "set_id",
            "transcript_file_id",
            name="uq_transcript_set_member",
        ),
        Index("idx_transcript_set_member_order", "set_id", "order_index"),
    )
