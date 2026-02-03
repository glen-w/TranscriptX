"""Group and group member database models."""

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
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
    func,
)


class Group(Base):
    """Persisted group definition (durable user object)."""

    __tablename__ = "groups"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = Column(String(36), unique=True, default=lambda: str(uuid4()))

    name: Mapped[Optional[str]] = Column(String(500), nullable=True, unique=True)
    type: Mapped[str] = Column(String(50), nullable=False, default="merged_event")
    key: Mapped[str] = Column(String(72), nullable=False, unique=True)
    description: Mapped[Optional[str]] = Column(Text, nullable=True)
    metadata_json: Mapped[Dict[str, Any]] = Column(JSONType, default=dict)

    created_at: Mapped[datetime] = Column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = Column(DateTime, default=func.now(), onupdate=func.now())

    members: Mapped[List["GroupMember"]] = relationship(
        "GroupMember", back_populates="group", cascade="all, delete"
    )

    __table_args__ = (
        Index("idx_groups_name", "name"),
        Index("idx_groups_type", "type"),
    )


class GroupMember(Base):
    """Ordered membership for a group."""

    __tablename__ = "group_members"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = Column(
        Integer,
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    transcript_file_id: Mapped[int] = Column(
        Integer,
        ForeignKey("transcript_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = Column(Integer, nullable=False)
    added_at: Mapped[datetime] = Column(DateTime, default=func.now())

    group: Mapped["Group"] = relationship("Group", back_populates="members")
    transcript_file: Mapped[Any] = relationship("TranscriptFile")

    __table_args__ = (
        UniqueConstraint(
            "group_id",
            "position",
            name="uq_group_member_position",
        ),
        UniqueConstraint(
            "group_id",
            "transcript_file_id",
            name="uq_group_member_transcript",
        ),
        Index("idx_group_member_position", "group_id", "position"),
    )
