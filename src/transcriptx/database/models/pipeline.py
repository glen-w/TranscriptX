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
    desc,
)
from datetime import datetime
from typing import Any, Dict, List, Optional


class PipelineRun(Base):
    """
    Pipeline execution container for one transcript and pipeline configuration.
    """

    __tablename__ = "pipeline_runs"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    transcript_file_id: Mapped[int] = Column(
        Integer,
        ForeignKey("transcript_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    pipeline_version: Mapped[Optional[str]] = Column(String(50), index=True)
    pipeline_config_hash: Mapped[Optional[str]] = Column(String(64), index=True)
    pipeline_input_hash: Mapped[Optional[str]] = Column(String(64), index=True)
    cli_args_json: Mapped[Optional[Dict[str, Any]]] = Column(JSONType, default=dict)

    status: Mapped[str] = Column(String(50), default="pending", index=True)
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    transcript_file: Mapped["TranscriptFile"] = relationship(
        "TranscriptFile", backref="pipeline_runs"
    )
    module_runs: Mapped[List["ModuleRun"]] = relationship(
        "ModuleRun", back_populates="pipeline_run"
    )

    __table_args__ = (
        Index("idx_pipeline_run_file", "transcript_file_id"),
        Index("idx_pipeline_run_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<PipelineRun(id={self.id}, transcript_file_id={self.transcript_file_id}, status='{self.status}')>"


class ModuleRun(Base):
    """
    Module execution record within a pipeline run.
    """

    __tablename__ = "module_runs"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    pipeline_run_id: Mapped[int] = Column(
        Integer,
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    transcript_file_id: Mapped[int] = Column(
        Integer,
        ForeignKey("transcript_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    module_name: Mapped[str] = Column(String(100), nullable=False, index=True)
    module_version: Mapped[Optional[str]] = Column(String(64), index=True)
    module_config_hash: Mapped[Optional[str]] = Column(String(64), index=True)
    module_input_hash: Mapped[Optional[str]] = Column(String(64), index=True)
    output_hash: Mapped[Optional[str]] = Column(String(64), index=True)

    status: Mapped[str] = Column(String(50), default="pending", index=True)
    duration_seconds: Mapped[Optional[float]] = Column(Float)
    is_cacheable: Mapped[bool] = Column(Boolean, default=True, index=True)
    cache_reason: Mapped[Optional[str]] = Column(String(255))

    metrics_json: Mapped[Dict[str, Any]] = Column(JSONType, default=dict)
    outputs_json: Mapped[Dict[str, Any]] = Column(JSONType, default=dict)

    replaces_module_run_id: Mapped[Optional[int]] = Column(
        Integer, ForeignKey("module_runs.id", ondelete="SET NULL")
    )
    superseded_at: Mapped[Optional[datetime]] = Column(DateTime)

    created_at: Mapped[datetime] = Column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = Column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    pipeline_run: Mapped["PipelineRun"] = relationship(
        "PipelineRun", back_populates="module_runs"
    )
    transcript_file: Mapped["TranscriptFile"] = relationship(
        "TranscriptFile", backref="module_runs"
    )
    artifacts: Mapped[List["ArtifactIndex"]] = relationship(
        "ArtifactIndex", back_populates="module_run"
    )
    replaces_module_run: Mapped[Optional["ModuleRun"]] = relationship(
        "ModuleRun", remote_side="ModuleRun.id"
    )

    __table_args__ = (
        Index("idx_module_run_pipeline", "pipeline_run_id"),
        Index("idx_module_run_module", "module_name"),
        Index("idx_module_run_input", "module_name", "module_input_hash"),
    )

    def __repr__(self) -> str:
        return f"<ModuleRun(id={self.id}, module='{self.module_name}', status='{self.status}')>"


class PerformanceSpan(Base):
    """
    Span-shaped performance log entry aligned with OpenTelemetry.
    """

    __tablename__ = "performance_spans"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)

    trace_id: Mapped[str] = Column(String(32), nullable=False, index=True)
    span_id: Mapped[str] = Column(String(16), nullable=False, unique=True, index=True)
    parent_span_id: Mapped[Optional[str]] = Column(String(16), index=True)

    name: Mapped[str] = Column(String(200), nullable=False, index=True)
    kind: Mapped[Optional[str]] = Column(String(20))

    status_code: Mapped[str] = Column(String(10), default="OK", index=True)
    status_message: Mapped[Optional[str]] = Column(Text)

    start_time: Mapped[datetime] = Column(DateTime, nullable=False, index=True)
    end_time: Mapped[Optional[datetime]] = Column(DateTime)
    duration_ms: Mapped[Optional[float]] = Column(Float)

    attributes_json: Mapped[Dict[str, Any]] = Column(JSONType, default=dict)
    events_json: Mapped[List[Dict[str, Any]]] = Column(JSONType, default=list)

    pipeline_run_id: Mapped[Optional[int]] = Column(
        Integer, ForeignKey("pipeline_runs.id", ondelete="SET NULL"), index=True
    )
    module_run_id: Mapped[Optional[int]] = Column(
        Integer, ForeignKey("module_runs.id", ondelete="SET NULL"), index=True
    )
    transcript_file_id: Mapped[Optional[int]] = Column(
        Integer, ForeignKey("transcript_files.id", ondelete="SET NULL"), index=True
    )

    created_at: Mapped[datetime] = Column(DateTime, default=func.now())

    __table_args__ = (
        Index("idx_span_start_time", desc("start_time")),
        Index("idx_span_name_start_time", "name", desc("start_time")),
        Index("idx_span_pipeline", "pipeline_run_id"),
        Index("idx_span_module", "module_run_id"),
        Index("idx_span_transcript", "transcript_file_id"),
    )

    def __repr__(self) -> str:
        return f"<PerformanceSpan(id={self.id}, name='{self.name}', status='{self.status_code}')>"


class ArtifactIndex(Base):
    """
    File-based artifacts registered with provenance.
    """

    __tablename__ = "artifact_index"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    module_run_id: Mapped[int] = Column(
        Integer,
        ForeignKey("module_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    transcript_file_id: Mapped[int] = Column(
        Integer,
        ForeignKey("transcript_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    artifact_key: Mapped[str] = Column(String(500), nullable=False)
    artifact_type: Mapped[Optional[str]] = Column(String(50), index=True)
    artifact_role: Mapped[str] = Column(String(50), default="primary", index=True)

    relative_path: Mapped[str] = Column(String(1000), nullable=False)
    artifact_root: Mapped[Optional[str]] = Column(String(1000))

    content_hash: Mapped[Optional[str]] = Column(String(64), index=True)
    created_at: Mapped[datetime] = Column(DateTime, default=func.now())
    exists_last_checked_at: Mapped[Optional[datetime]] = Column(DateTime)

    module_run: Mapped["ModuleRun"] = relationship(
        "ModuleRun", back_populates="artifacts"
    )
    transcript_file: Mapped["TranscriptFile"] = relationship(
        "TranscriptFile", backref="artifacts"
    )

    __table_args__ = (
        UniqueConstraint(
            "module_run_id", "artifact_key", name="uq_module_run_artifact_key"
        ),
        Index("idx_artifact_transcript", "transcript_file_id"),
        Index("idx_artifact_content", "content_hash"),
    )

    def __repr__(self) -> str:
        return f"<ArtifactIndex(id={self.id}, key='{self.artifact_key}')>"
