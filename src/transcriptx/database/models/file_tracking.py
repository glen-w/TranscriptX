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
    event,
)
from datetime import datetime
from typing import Any, Dict, List, Optional


class FileEntity(Base):
    """
    File entity representing content-based identity for audio files.

    This model stores the unique identity of a file based on its audio fingerprint hash.
    One row per unique audio content, regardless of paths or names.
    """

    __tablename__ = "file_entities"

    # Primary key
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)

    # Fingerprint-based identity
    fingerprint_hash: Mapped[str] = Column(
        String(64), unique=True, nullable=False, index=True
    )
    fingerprint_vector: Mapped[List[float]] = Column(
        JSONType, nullable=False
    )  # 12-dim array as JSON
    fingerprint_version: Mapped[int] = Column(Integer, default=1, nullable=False)

    # Timestamps
    first_seen_at: Mapped[datetime] = Column(
        DateTime, default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = Column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    # Intrinsic properties
    duration_seconds: Mapped[Optional[float]] = Column(Float)

    # Soft deletion
    deleted_at: Mapped[Optional[datetime]] = Column(DateTime, nullable=True)

    # Metadata (renamed from 'metadata' to avoid SQLAlchemy reserved name conflict)
    file_metadata: Mapped[Dict[str, Any]] = Column(JSONType, default=dict)
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # Relationships
    artifacts: Mapped[List["FileArtifact"]] = relationship(
        "FileArtifact", back_populates="file_entity", cascade="all, delete-orphan"
    )
    events: Mapped[List["FileProcessingEvent"]] = relationship(
        "FileProcessingEvent", back_populates="file_entity"
    )
    preprocessing_records: Mapped[List["FilePreprocessingRecord"]] = relationship(
        "FilePreprocessingRecord", back_populates="file_entity"
    )
    rename_history: Mapped[List["FileRenameHistory"]] = relationship(
        "FileRenameHistory", back_populates="file_entity"
    )

    # Indexes
    __table_args__ = (
        Index("idx_file_entity_fingerprint", "fingerprint_hash"),
        Index("idx_file_entity_first_seen", "first_seen_at"),
        Index("idx_file_entity_last_seen", "last_seen_at"),
    )

    def __repr__(self) -> str:
        return f"<FileEntity(id={self.id}, fingerprint_hash='{self.fingerprint_hash[:16]}...')>"


class FileArtifact(Base):
    """
    File artifact representing a concrete file/location for a FileEntity.

    Tracks multiple concrete files/paths for the same entity over time.
    Handles original WAV, processed WAV, MP3, transcript, backup, temp files.
    """

    __tablename__ = "file_artifacts"

    # Primary key
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign key
    file_entity_id: Mapped[int] = Column(
        Integer,
        ForeignKey("file_entities.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # File information
    path: Mapped[str] = Column(String(1000), nullable=False, index=True)
    file_type: Mapped[str] = Column(String(50), nullable=False)
    role: Mapped[str] = Column(
        String(50), nullable=False, index=True
    )  # original, processed_wav, mp3, transcript, backup, temp, etc.

    # File properties
    size_bytes: Mapped[Optional[int]] = Column(Integer)
    mtime: Mapped[Optional[datetime]] = Column(DateTime)
    checksum: Mapped[Optional[str]] = Column(String(64))

    # Status flags
    is_current: Mapped[bool] = Column(
        Boolean, default=False, nullable=False, index=True
    )
    is_present: Mapped[bool] = Column(Boolean, default=True, nullable=False, index=True)

    # Metadata (renamed from 'metadata' to avoid SQLAlchemy reserved name conflict)
    file_metadata: Mapped[Dict[str, Any]] = Column(JSONType, default=dict)
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # Relationships
    file_entity: Mapped["FileEntity"] = relationship(
        "FileEntity", back_populates="artifacts"
    )
    source_events: Mapped[List["FileProcessingEvent"]] = relationship(
        "FileProcessingEvent",
        foreign_keys="FileProcessingEvent.source_artifact_id",
        back_populates="source_artifact",
    )
    target_events: Mapped[List["FileProcessingEvent"]] = relationship(
        "FileProcessingEvent",
        foreign_keys="FileProcessingEvent.target_artifact_id",
        back_populates="target_artifact",
    )
    rename_history: Mapped[List["FileRenameHistory"]] = relationship(
        "FileRenameHistory", back_populates="artifact"
    )

    # Indexes
    __table_args__ = (
        Index("idx_artifact_entity", "file_entity_id"),
        Index("idx_artifact_path", "path"),
        Index("idx_artifact_role_current", "role", "is_current"),
        Index("idx_artifact_present", "is_present"),
    )

    def __repr__(self) -> str:
        return f"<FileArtifact(id={self.id}, file_entity_id={self.file_entity_id}, role='{self.role}', path='{self.path[:50]}...')>"


class FileProcessingEvent(Base):
    """
    File processing event representing an operation on a file.

    Immutable audit log of all processing operations. Events reference artifacts,
    not just paths. Events are append-only (no deletes); status/timestamps may be
    updated for lifecycle transitions.
    """

    __tablename__ = "file_processing_events"

    # Primary key
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)

    # Unique identifier for idempotency
    event_uuid: Mapped[str] = Column(
        String(36), unique=True, nullable=False, index=True
    )

    # Foreign keys
    file_entity_id: Mapped[int] = Column(
        Integer,
        ForeignKey("file_entities.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source_artifact_id: Mapped[Optional[int]] = Column(
        Integer, ForeignKey("file_artifacts.id", ondelete="SET NULL"), nullable=True
    )
    target_artifact_id: Mapped[Optional[int]] = Column(
        Integer, ForeignKey("file_artifacts.id", ondelete="SET NULL"), nullable=True
    )

    # Event metadata
    pipeline_run_id: Mapped[Optional[str]] = Column(
        String(100), nullable=True, index=True
    )
    event_type: Mapped[str] = Column(
        String(50), nullable=False, index=True
    )  # ingestion, preprocessing, conversion, transcription, rename, backup, move, delete, analysis
    event_status: Mapped[str] = Column(
        String(50), nullable=False, index=True
    )  # pending, in_progress, completed, failed

    # Denormalized paths (for convenience)
    source_path: Mapped[Optional[str]] = Column(String(1000))
    target_path: Mapped[Optional[str]] = Column(String(1000))

    # Operation details
    operation_details: Mapped[Dict[str, Any]] = Column(JSONType, default=dict)
    error_message: Mapped[Optional[str]] = Column(Text)
    processing_time_seconds: Mapped[Optional[float]] = Column(Float)

    # Timestamps
    started_at: Mapped[Optional[datetime]] = Column(DateTime)
    completed_at: Mapped[Optional[datetime]] = Column(DateTime)
    performed_by: Mapped[Optional[str]] = Column(String(100))
    created_at: Mapped[datetime] = Column(DateTime, default=func.now(), index=True)

    # Relationships
    file_entity: Mapped["FileEntity"] = relationship(
        "FileEntity", back_populates="events"
    )
    source_artifact: Mapped[Optional["FileArtifact"]] = relationship(
        "FileArtifact",
        foreign_keys=[source_artifact_id],
        back_populates="source_events",
    )
    target_artifact: Mapped[Optional["FileArtifact"]] = relationship(
        "FileArtifact",
        foreign_keys=[target_artifact_id],
        back_populates="target_events",
    )
    preprocessing_record: Mapped[Optional["FilePreprocessingRecord"]] = relationship(
        "FilePreprocessingRecord", back_populates="processing_event", uselist=False
    )
    rename_history: Mapped[List["FileRenameHistory"]] = relationship(
        "FileRenameHistory", back_populates="processing_event"
    )

    # Indexes
    __table_args__ = (
        Index("idx_event_uuid", "event_uuid"),
        Index("idx_event_entity", "file_entity_id"),
        Index("idx_event_pipeline", "pipeline_run_id"),
        Index("idx_event_type_status", "event_type", "event_status"),
        Index("idx_event_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<FileProcessingEvent(id={self.id}, event_type='{self.event_type}', status='{self.event_status}')>"


class FilePreprocessingRecord(Base):
    """
    Preprocessing record storing detailed preprocessing information.

    Links preprocessing events with detailed preprocessing data including
    summary and full JSON configuration.
    """

    __tablename__ = "file_preprocessing_records"

    # Primary key
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    file_entity_id: Mapped[int] = Column(
        Integer, ForeignKey("file_entities.id", ondelete="RESTRICT"), nullable=False
    )
    processing_event_id: Mapped[int] = Column(
        Integer,
        ForeignKey("file_processing_events.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    source_artifact_id: Mapped[Optional[int]] = Column(
        Integer, ForeignKey("file_artifacts.id", ondelete="SET NULL"), nullable=True
    )
    target_artifact_id: Mapped[Optional[int]] = Column(
        Integer, ForeignKey("file_artifacts.id", ondelete="SET NULL"), nullable=True
    )

    # Preprocessing data
    preprocessing_summary: Mapped[Dict[str, Any]] = Column(
        JSONType, default=dict
    )  # {"denoise": true, "highpass": true, ...}
    preprocessing_full_json: Mapped[Dict[str, Any]] = Column(
        JSONType, default=dict
    )  # Complete preprocessing JSON
    original_file_size_bytes: Mapped[Optional[int]] = Column(Integer)
    processed_file_size_bytes: Mapped[Optional[int]] = Column(Integer)
    applied_steps: Mapped[List[str]] = Column(
        JSONType, default=list
    )  # ["denoise", "highpass"]

    # Timestamp
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())

    # Relationships
    file_entity: Mapped["FileEntity"] = relationship(
        "FileEntity", back_populates="preprocessing_records"
    )
    processing_event: Mapped["FileProcessingEvent"] = relationship(
        "FileProcessingEvent", back_populates="preprocessing_record"
    )

    # Indexes
    __table_args__ = (
        Index("idx_preprocessing_entity", "file_entity_id"),
        Index("idx_preprocessing_event", "processing_event_id"),
    )

    def __repr__(self) -> str:
        return f"<FilePreprocessingRecord(id={self.id}, file_entity_id={self.file_entity_id}, event_id={self.processing_event_id})>"


class FileRenameHistory(Base):
    """
    Rename history tracking rename operations with transaction grouping.

    Tracks all rename operations for audit trail, with support for
    grouping multi-file renames in one transaction.
    """

    __tablename__ = "file_rename_history"

    # Primary key
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    file_entity_id: Mapped[int] = Column(
        Integer, ForeignKey("file_entities.id", ondelete="RESTRICT"), nullable=False
    )
    processing_event_id: Mapped[int] = Column(
        Integer,
        ForeignKey("file_processing_events.id", ondelete="RESTRICT"),
        nullable=False,
    )
    artifact_id: Mapped[int] = Column(
        Integer, ForeignKey("file_artifacts.id", ondelete="RESTRICT"), nullable=False
    )

    # Rename grouping
    rename_group_id: Mapped[str] = Column(
        String(36), nullable=False, index=True
    )  # UUID for grouping multi-file renames

    # Rename details
    old_path: Mapped[str] = Column(String(1000), nullable=False)
    new_path: Mapped[str] = Column(String(1000), nullable=False)
    old_name: Mapped[str] = Column(String(500), nullable=False)
    new_name: Mapped[str] = Column(String(500), nullable=False)
    rename_reason: Mapped[Optional[str]] = Column(String(255))
    renamed_files: Mapped[List[Dict[str, str]]] = Column(
        JSONType, default=list
    )  # Array of {"old": "...", "new": "..."}

    # Timestamp
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())

    # Relationships
    file_entity: Mapped["FileEntity"] = relationship(
        "FileEntity", back_populates="rename_history"
    )
    processing_event: Mapped["FileProcessingEvent"] = relationship(
        "FileProcessingEvent", back_populates="rename_history"
    )
    artifact: Mapped["FileArtifact"] = relationship(
        "FileArtifact", back_populates="rename_history"
    )

    # Indexes
    __table_args__ = (
        Index("idx_rename_entity", "file_entity_id"),
        Index("idx_rename_event", "processing_event_id"),
        Index("idx_rename_group", "rename_group_id"),
        Index("idx_rename_artifact", "artifact_id"),
    )

    def __repr__(self) -> str:
        return f"<FileRenameHistory(id={self.id}, artifact_id={self.artifact_id}, old_name='{self.old_name}', new_name='{self.new_name}')>"


# Event listeners for automatic timestamp updates
@event.listens_for(Base, "before_update", propagate=True)
def timestamp_before_update(mapper, connection, target):
    """Automatically update the updated_at timestamp before any update."""
    target.updated_at = func.now()
