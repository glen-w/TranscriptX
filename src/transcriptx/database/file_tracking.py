"""
File tracking service for TranscriptX.

This module provides the core FileTrackingService that enforces invariants
for file tracking with single-entity identity and artifact management.

Key Features:
- Single entity per fingerprint hash (enforced)
- Artifact management with current flag enforcement
- Event logging with idempotency
- Complete file history tracking
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from transcriptx.core.utils.logger import get_logger
from .repositories import (
    FileEntityRepository,
    FileArtifactRepository,
    FileProcessingEventRepository,
    FileHistoryRepository,
)
from .models import FileEntity, FileArtifact, FileProcessingEvent

logger = get_logger()


class FileTrackingService:
    """
    Core service for file tracking with invariant enforcement.

    This service enforces:
    - Single entity per fingerprint hash
    - No entity proliferation after ingestion
    - Artifact current flag management
    - Event immutability rules
    - Last seen timestamp updates
    """

    def __init__(self, session: Session):
        """
        Initialize file tracking service.

        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.entity_repo = FileEntityRepository(session)
        self.artifact_repo = FileArtifactRepository(session)
        self.event_repo = FileProcessingEventRepository(session)
        self.history_repo = FileHistoryRepository(session)

    def get_or_create_file_entity(
        self,
        fingerprint_hash: str,
        fingerprint_vector: List[float],
        fingerprint_version: int = 1,
        duration_seconds: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FileEntity:
        """
        Get existing or create new file entity.

        ENFORCES: Single entity per fingerprint hash.
        Returns existing entity if fingerprint_hash exists.

        Args:
            fingerprint_hash: SHA256 hash of canonicalized fingerprint
            fingerprint_vector: 12-dimensional fingerprint array
            fingerprint_version: Version of fingerprint algorithm (default: 1)
            duration_seconds: Audio duration in seconds
            metadata: Additional metadata

        Returns:
            FileEntity instance (existing or newly created)
        """
        # Check if entity already exists
        entity = self.entity_repo.find_by_fingerprint_hash(fingerprint_hash)

        if entity:
            logger.debug(
                f"Found existing file entity: {entity.id} (hash: {fingerprint_hash[:16]}...)"
            )
            return entity

        # Create new entity
        logger.info(
            f"Creating new file entity for fingerprint hash: {fingerprint_hash[:16]}..."
        )
        return self.entity_repo.create_file_entity(
            fingerprint_hash=fingerprint_hash,
            fingerprint_vector=fingerprint_vector,
            fingerprint_version=fingerprint_version,
            duration_seconds=duration_seconds,
            metadata=metadata,
        )

    def create_artifact(
        self,
        file_entity_id: int,
        path: str,
        file_type: str,
        role: str,
        size_bytes: Optional[int] = None,
        mtime: Optional[datetime] = None,
        checksum: Optional[str] = None,
        is_current: bool = False,
        is_present: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FileArtifact:
        """
        Create a new file artifact.

        ENFORCES: If is_current=True, unsets other current artifacts for same (entity, role).

        Args:
            file_entity_id: ID of the file entity
            path: Full filesystem path
            file_type: File type (wav, mp3, transcript, json, etc.)
            role: Artifact role (original, processed_wav, mp3, transcript, backup, etc.)
            size_bytes: File size in bytes
            mtime: File modification time
            checksum: Optional file checksum
            is_current: Whether this is the current artifact for this role
            is_present: Whether file exists on filesystem
            metadata: Additional metadata

        Returns:
            Created FileArtifact instance
        """
        artifact = self.artifact_repo.create_artifact(
            file_entity_id=file_entity_id,
            path=path,
            file_type=file_type,
            role=role,
            size_bytes=size_bytes,
            mtime=mtime,
            checksum=checksum,
            is_current=False,  # Set to False first, then set_current if needed
            is_present=is_present,
            metadata=metadata,
        )

        # Enforce single current artifact per (entity, role)
        if is_current:
            self.artifact_repo.set_current(artifact.id, file_entity_id, role)

        return artifact

    def log_ingestion(
        self,
        file_entity_id: int,
        artifact_id: int,
        pipeline_run_id: Optional[str] = None,
        operation_details: Optional[Dict[str, Any]] = None,
        performed_by: Optional[str] = None,
    ) -> FileProcessingEvent:
        """
        Log file ingestion event.

        Args:
            file_entity_id: ID of the file entity
            artifact_id: ID of the original artifact
            pipeline_run_id: Optional pipeline run ID
            operation_details: Operation-specific data
            performed_by: User/system identifier

        Returns:
            Created FileProcessingEvent instance
        """
        artifact = (
            self.session.query(FileArtifact)
            .filter(FileArtifact.id == artifact_id)
            .first()
        )

        event = self.event_repo.create_event(
            event_uuid=str(uuid4()),
            file_entity_id=file_entity_id,
            event_type="ingestion",
            event_status="completed",
            target_artifact_id=artifact_id,
            pipeline_run_id=pipeline_run_id,
            target_path=artifact.path if artifact else None,
            operation_details=operation_details,
            performed_by=performed_by,
            completed_at=datetime.now(),
        )

        # Update last_seen_at
        self.entity_repo.update_last_seen(file_entity_id)

        return event

    def log_preprocessing(
        self,
        file_entity_id: int,
        source_artifact_id: int,
        target_artifact_id: int,
        preprocessing_summary: Dict[str, Any],
        preprocessing_full_json: Dict[str, Any],
        original_file_size_bytes: Optional[int] = None,
        processed_file_size_bytes: Optional[int] = None,
        applied_steps: Optional[List[str]] = None,
        pipeline_run_id: Optional[str] = None,
        operation_details: Optional[Dict[str, Any]] = None,
    ) -> FileProcessingEvent:
        """
        Log preprocessing event and create preprocessing record.

        Args:
            file_entity_id: ID of the file entity
            source_artifact_id: ID of original WAV artifact
            target_artifact_id: ID of processed WAV artifact
            preprocessing_summary: Summary of preprocessing steps
            preprocessing_full_json: Complete preprocessing JSON
            original_file_size_bytes: Original file size
            processed_file_size_bytes: Processed file size
            applied_steps: List of applied steps
            pipeline_run_id: Optional pipeline run ID
            operation_details: Operation-specific data

        Returns:
            Created FileProcessingEvent instance
        """
        from .models import FilePreprocessingRecord

        source_artifact = (
            self.session.query(FileArtifact)
            .filter(FileArtifact.id == source_artifact_id)
            .first()
        )
        target_artifact = (
            self.session.query(FileArtifact)
            .filter(FileArtifact.id == target_artifact_id)
            .first()
        )

        event = self.event_repo.create_event(
            event_uuid=str(uuid4()),
            file_entity_id=file_entity_id,
            event_type="preprocessing",
            event_status="completed",
            source_artifact_id=source_artifact_id,
            target_artifact_id=target_artifact_id,
            pipeline_run_id=pipeline_run_id,
            source_path=source_artifact.path if source_artifact else None,
            target_path=target_artifact.path if target_artifact else None,
            operation_details=operation_details,
            completed_at=datetime.now(),
        )

        # Create preprocessing record
        record = FilePreprocessingRecord(
            file_entity_id=file_entity_id,
            processing_event_id=event.id,
            source_artifact_id=source_artifact_id,
            target_artifact_id=target_artifact_id,
            preprocessing_summary=preprocessing_summary,
            preprocessing_full_json=preprocessing_full_json,
            original_file_size_bytes=original_file_size_bytes,
            processed_file_size_bytes=processed_file_size_bytes,
            applied_steps=applied_steps or [],
        )
        self.session.add(record)
        self.session.flush()

        # Update last_seen_at
        self.entity_repo.update_last_seen(file_entity_id)

        return event

    def log_conversion(
        self,
        file_entity_id: int,
        source_artifact_id: int,
        target_artifact_id: int,
        pipeline_run_id: Optional[str] = None,
        operation_details: Optional[Dict[str, Any]] = None,
    ) -> FileProcessingEvent:
        """
        Log conversion event (WAV → MP3).

        Args:
            file_entity_id: ID of the file entity
            source_artifact_id: ID of source artifact (WAV)
            target_artifact_id: ID of target artifact (MP3)
            pipeline_run_id: Optional pipeline run ID
            operation_details: Operation-specific data

        Returns:
            Created FileProcessingEvent instance
        """
        source_artifact = (
            self.session.query(FileArtifact)
            .filter(FileArtifact.id == source_artifact_id)
            .first()
        )
        target_artifact = (
            self.session.query(FileArtifact)
            .filter(FileArtifact.id == target_artifact_id)
            .first()
        )

        event = self.event_repo.create_event(
            event_uuid=str(uuid4()),
            file_entity_id=file_entity_id,
            event_type="conversion",
            event_status="completed",
            source_artifact_id=source_artifact_id,
            target_artifact_id=target_artifact_id,
            pipeline_run_id=pipeline_run_id,
            source_path=source_artifact.path if source_artifact else None,
            target_path=target_artifact.path if target_artifact else None,
            operation_details=operation_details,
            completed_at=datetime.now(),
        )

        # Update last_seen_at
        self.entity_repo.update_last_seen(file_entity_id)

        return event

    def log_transcription(
        self,
        file_entity_id: int,
        source_artifact_id: int,
        target_artifact_id: int,
        pipeline_run_id: Optional[str] = None,
        operation_details: Optional[Dict[str, Any]] = None,
    ) -> FileProcessingEvent:
        """
        Log transcription event (MP3 → transcript).

        Args:
            file_entity_id: ID of the file entity
            source_artifact_id: ID of source artifact (MP3)
            target_artifact_id: ID of target artifact (transcript)
            pipeline_run_id: Optional pipeline run ID
            operation_details: Operation-specific data

        Returns:
            Created FileProcessingEvent instance
        """
        source_artifact = (
            self.session.query(FileArtifact)
            .filter(FileArtifact.id == source_artifact_id)
            .first()
        )
        target_artifact = (
            self.session.query(FileArtifact)
            .filter(FileArtifact.id == target_artifact_id)
            .first()
        )

        event = self.event_repo.create_event(
            event_uuid=str(uuid4()),
            file_entity_id=file_entity_id,
            event_type="transcription",
            event_status="completed",
            source_artifact_id=source_artifact_id,
            target_artifact_id=target_artifact_id,
            pipeline_run_id=pipeline_run_id,
            source_path=source_artifact.path if source_artifact else None,
            target_path=target_artifact.path if target_artifact else None,
            operation_details=operation_details,
            completed_at=datetime.now(),
        )

        # Update last_seen_at
        self.entity_repo.update_last_seen(file_entity_id)

        return event

    def log_rename(
        self,
        file_entity_id: int,
        artifact_id: int,
        old_path: str,
        new_path: str,
        old_name: str,
        new_name: str,
        rename_group_id: str,
        rename_reason: Optional[str] = None,
        renamed_files: Optional[List[Dict[str, str]]] = None,
        pipeline_run_id: Optional[str] = None,
    ) -> FileProcessingEvent:
        """
        Log rename event and create rename history record.

        Args:
            file_entity_id: ID of the file entity
            artifact_id: ID of the artifact being renamed
            old_path: Old filesystem path
            new_path: New filesystem path
            old_name: Old base filename
            new_name: New base filename
            rename_group_id: UUID for grouping multi-file renames
            rename_reason: Optional reason for rename
            renamed_files: Array of all files renamed in transaction
            pipeline_run_id: Optional pipeline run ID

        Returns:
            Created FileProcessingEvent instance
        """
        from .models import FileRenameHistory

        # Update artifact path
        self.artifact_repo.update_path(artifact_id, new_path)

        # Create event
        event = self.event_repo.create_event(
            event_uuid=str(uuid4()),
            file_entity_id=file_entity_id,
            event_type="rename",
            event_status="completed",
            source_artifact_id=artifact_id,
            target_artifact_id=artifact_id,  # Same artifact, path updated
            pipeline_run_id=pipeline_run_id,
            source_path=old_path,
            target_path=new_path,
            operation_details={"rename_group_id": rename_group_id},
            completed_at=datetime.now(),
        )

        # Create rename history record
        history = FileRenameHistory(
            file_entity_id=file_entity_id,
            processing_event_id=event.id,
            artifact_id=artifact_id,
            rename_group_id=rename_group_id,
            old_path=old_path,
            new_path=new_path,
            old_name=old_name,
            new_name=new_name,
            rename_reason=rename_reason,
            renamed_files=renamed_files or [],
        )
        self.session.add(history)
        self.session.flush()

        # Update last_seen_at
        self.entity_repo.update_last_seen(file_entity_id)

        return event

    def log_backup(
        self,
        file_entity_id: int,
        source_artifact_id: int,
        target_artifact_id: int,
        pipeline_run_id: Optional[str] = None,
        operation_details: Optional[Dict[str, Any]] = None,
    ) -> FileProcessingEvent:
        """
        Log backup event.

        Args:
            file_entity_id: ID of the file entity
            source_artifact_id: ID of source artifact
            target_artifact_id: ID of backup artifact
            pipeline_run_id: Optional pipeline run ID
            operation_details: Operation-specific data

        Returns:
            Created FileProcessingEvent instance
        """
        source_artifact = (
            self.session.query(FileArtifact)
            .filter(FileArtifact.id == source_artifact_id)
            .first()
        )
        target_artifact = (
            self.session.query(FileArtifact)
            .filter(FileArtifact.id == target_artifact_id)
            .first()
        )

        event = self.event_repo.create_event(
            event_uuid=str(uuid4()),
            file_entity_id=file_entity_id,
            event_type="backup",
            event_status="completed",
            source_artifact_id=source_artifact_id,
            target_artifact_id=target_artifact_id,
            pipeline_run_id=pipeline_run_id,
            source_path=source_artifact.path if source_artifact else None,
            target_path=target_artifact.path if target_artifact else None,
            operation_details=operation_details,
            completed_at=datetime.now(),
        )

        # Update last_seen_at
        self.entity_repo.update_last_seen(file_entity_id)

        return event

    def get_file_history(
        self,
        file_entity_id: int,
        include_artifacts: bool = True,
        include_events: bool = True,
    ) -> Dict[str, Any]:
        """
        Get complete history for a file entity.

        Args:
            file_entity_id: ID of the file entity
            include_artifacts: Whether to include artifacts
            include_events: Whether to include events

        Returns:
            Dictionary with entity, artifacts, and events
        """
        return self.history_repo.get_file_history(
            file_entity_id,
            include_artifacts=include_artifacts,
            include_events=include_events,
        )

    def find_file_by_fingerprint(self, fingerprint_hash: str) -> Optional[FileEntity]:
        """
        Find file entity by fingerprint hash.

        Args:
            fingerprint_hash: SHA256 hash of canonicalized fingerprint

        Returns:
            FileEntity if found, None otherwise
        """
        return self.entity_repo.find_by_fingerprint_hash(fingerprint_hash)

    def get_current_artifacts(
        self, file_entity_id: int, role: Optional[str] = None
    ) -> List[FileArtifact]:
        """
        Get current artifacts for a file entity.

        Args:
            file_entity_id: ID of the file entity
            role: Optional role filter

        Returns:
            List of current FileArtifact instances
        """
        return self.history_repo.get_current_artifacts(file_entity_id, role=role)
