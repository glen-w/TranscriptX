"""
Repository classes for TranscriptX database operations.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func

from transcriptx.core.utils.logger import get_logger
from ..models import FileEntity, FileArtifact, FileProcessingEvent

logger = get_logger()


from .base import BaseRepository


class FileEntityRepository(BaseRepository):
    """
    Repository for file entity operations.

    Provides methods for managing file entities based on fingerprint hash.
    """

    def find_by_fingerprint_hash(self, fingerprint_hash: str) -> Optional[FileEntity]:
        """
        Find file entity by fingerprint hash.

        Args:
            fingerprint_hash: SHA256 hash of canonicalized fingerprint

        Returns:
            FileEntity if found, None otherwise
        """
        try:
            return (
                self.session.query(FileEntity)
                .filter(FileEntity.fingerprint_hash == fingerprint_hash)
                .first()
            )
        except Exception as e:
            self._handle_error("find_by_fingerprint_hash", e)

    def create_file_entity(
        self,
        fingerprint_hash: str,
        fingerprint_vector: List[float],
        fingerprint_version: int = 1,
        duration_seconds: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FileEntity:
        """
        Create a new file entity.

        Args:
            fingerprint_hash: SHA256 hash of canonicalized fingerprint
            fingerprint_vector: 12-dimensional fingerprint array
            fingerprint_version: Version of fingerprint algorithm (default: 1)
            duration_seconds: Audio duration in seconds
            metadata: Additional metadata

        Returns:
            Created FileEntity instance
        """
        try:
            entity = FileEntity(
                fingerprint_hash=fingerprint_hash,
                fingerprint_vector=fingerprint_vector,
                fingerprint_version=fingerprint_version,
                duration_seconds=duration_seconds,
                file_metadata=metadata or {},
            )
            self.session.add(entity)
            self.session.flush()
            logger.info(
                f"✅ Created file entity with fingerprint hash: {fingerprint_hash[:16]}..."
            )
            return entity
        except Exception as e:
            self._handle_error("create_file_entity", e)

    def update_last_seen(self, file_entity_id: int) -> None:
        """
        Update last_seen_at timestamp for a file entity.

        Args:
            file_entity_id: ID of the file entity
        """
        try:
            entity = (
                self.session.query(FileEntity)
                .filter(FileEntity.id == file_entity_id)
                .first()
            )
            if entity:
                entity.last_seen_at = func.now()
                self.session.flush()
        except Exception as e:
            self._handle_error("update_last_seen", e)


class FileArtifactRepository(BaseRepository):
    """
    Repository for file artifact operations.

    Provides methods for managing file artifacts (concrete files/paths).
    """

    def find_by_path(self, path: str) -> Optional[FileArtifact]:
        """
        Find artifact by filesystem path.

        Args:
            path: Full filesystem path

        Returns:
            FileArtifact if found, None otherwise
        """
        try:
            return (
                self.session.query(FileArtifact)
                .filter(FileArtifact.path == path)
                .first()
            )
        except Exception as e:
            self._handle_error("find_by_path", e)

    def find_current_by_role(
        self, file_entity_id: int, role: str
    ) -> Optional[FileArtifact]:
        """
        Find current artifact for a given entity and role.

        Args:
            file_entity_id: ID of the file entity
            role: Artifact role (original, processed_wav, mp3, transcript, etc.)

        Returns:
            Current FileArtifact if found, None otherwise
        """
        try:
            return (
                self.session.query(FileArtifact)
                .filter(
                    and_(
                        FileArtifact.file_entity_id == file_entity_id,
                        FileArtifact.role == role,
                        FileArtifact.is_current == True,
                    )
                )
                .first()
            )
        except Exception as e:
            self._handle_error("find_current_by_role", e)

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
        try:
            artifact = FileArtifact(
                file_entity_id=file_entity_id,
                path=path,
                file_type=file_type,
                role=role,
                size_bytes=size_bytes,
                mtime=mtime,
                checksum=checksum,
                is_current=is_current,
                is_present=is_present,
                file_metadata=metadata or {},
            )
            self.session.add(artifact)
            self.session.flush()
            logger.debug(f"✅ Created artifact: {role} at {path}")
            return artifact
        except Exception as e:
            self._handle_error("create_artifact", e)

    def update_path(self, artifact_id: int, new_path: str) -> None:
        """
        Update artifact path (for rename operations).

        Args:
            artifact_id: ID of the artifact
            new_path: New filesystem path
        """
        try:
            artifact = (
                self.session.query(FileArtifact)
                .filter(FileArtifact.id == artifact_id)
                .first()
            )
            if artifact:
                artifact.path = new_path
                self.session.flush()
        except Exception as e:
            self._handle_error("update_path", e)

    def set_current(self, artifact_id: int, file_entity_id: int, role: str) -> None:
        """
        Set artifact as current for its role, unsetting others.

        This enforces the invariant: only one current artifact per (entity, role).

        Args:
            artifact_id: ID of the artifact to set as current
            file_entity_id: ID of the file entity
            role: Artifact role
        """
        try:
            # Unset all current artifacts for this (entity, role)
            self.session.query(FileArtifact).filter(
                and_(
                    FileArtifact.file_entity_id == file_entity_id,
                    FileArtifact.role == role,
                    FileArtifact.is_current == True,
                )
            ).update({"is_current": False})

            # Set the specified artifact as current
            artifact = (
                self.session.query(FileArtifact)
                .filter(FileArtifact.id == artifact_id)
                .first()
            )
            if artifact:
                artifact.is_current = True
                self.session.flush()
        except Exception as e:
            self._handle_error("set_current", e)

    def get_artifacts_by_entity(
        self,
        file_entity_id: int,
        role: Optional[str] = None,
        is_current: Optional[bool] = None,
    ) -> List[FileArtifact]:
        """
        Get artifacts for a file entity.

        Args:
            file_entity_id: ID of the file entity
            role: Optional role filter
            is_current: Optional current flag filter

        Returns:
            List of FileArtifact instances
        """
        try:
            query = self.session.query(FileArtifact).filter(
                FileArtifact.file_entity_id == file_entity_id
            )

            if role:
                query = query.filter(FileArtifact.role == role)

            if is_current is not None:
                query = query.filter(FileArtifact.is_current == is_current)

            return query.order_by(FileArtifact.created_at.desc()).all()
        except Exception as e:
            self._handle_error("get_artifacts_by_entity", e)


class FileProcessingEventRepository(BaseRepository):
    """
    Repository for file processing event operations.

    Provides methods for logging and querying processing events.
    """

    def find_by_uuid(self, event_uuid: str) -> Optional[FileProcessingEvent]:
        """
        Find event by UUID (for idempotency).

        Args:
            event_uuid: Event UUID

        Returns:
            FileProcessingEvent if found, None otherwise
        """
        try:
            return (
                self.session.query(FileProcessingEvent)
                .filter(FileProcessingEvent.event_uuid == event_uuid)
                .first()
            )
        except Exception as e:
            self._handle_error("find_by_uuid", e)

    def create_event(
        self,
        event_uuid: str,
        file_entity_id: int,
        event_type: str,
        event_status: str = "pending",
        source_artifact_id: Optional[int] = None,
        target_artifact_id: Optional[int] = None,
        pipeline_run_id: Optional[str] = None,
        source_path: Optional[str] = None,
        target_path: Optional[str] = None,
        operation_details: Optional[Dict[str, Any]] = None,
        performed_by: Optional[str] = None,
    ) -> FileProcessingEvent:
        """
        Create a new processing event.

        Args:
            event_uuid: Unique event UUID for idempotency
            file_entity_id: ID of the file entity
            event_type: Type of event (ingestion, preprocessing, conversion, etc.)
            event_status: Event status (pending, in_progress, completed, failed)
            source_artifact_id: ID of source artifact (before operation)
            target_artifact_id: ID of target artifact (after operation)
            pipeline_run_id: ID grouping events from same processing run
            source_path: Denormalized source path
            target_path: Denormalized target path
            operation_details: Operation-specific data
            performed_by: User/system identifier

        Returns:
            Created FileProcessingEvent instance
        """
        try:
            event = FileProcessingEvent(
                event_uuid=event_uuid,
                file_entity_id=file_entity_id,
                event_type=event_type,
                event_status=event_status,
                source_artifact_id=source_artifact_id,
                target_artifact_id=target_artifact_id,
                pipeline_run_id=pipeline_run_id,
                source_path=source_path,
                target_path=target_path,
                operation_details=operation_details or {},
                performed_by=performed_by,
            )
            self.session.add(event)
            self.session.flush()
            logger.debug(f"✅ Created event: {event_type} ({event_status})")
            return event
        except Exception as e:
            self._handle_error("create_event", e)

    def update_event_status(
        self,
        event_id: int,
        event_status: str,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        processing_time_seconds: Optional[float] = None,
        error_message: Optional[str] = None,
        operation_details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Update event status and timestamps.

        Only allows updates if event is not yet completed/failed.

        Args:
            event_id: ID of the event
            event_status: New event status
            started_at: When operation started
            completed_at: When operation completed
            processing_time_seconds: Processing time in seconds
            error_message: Error message if failed
            operation_details: Updated operation details
        """
        try:
            event = (
                self.session.query(FileProcessingEvent)
                .filter(FileProcessingEvent.id == event_id)
                .first()
            )

            if not event:
                raise ValueError(f"Event {event_id} not found")

            # Enforce immutability after completed/failed
            if event.event_status in ("completed", "failed"):
                raise ValueError(
                    f"Cannot update event {event_id} with status {event.event_status}"
                )

            event.event_status = event_status
            if started_at:
                event.started_at = started_at
            if completed_at:
                event.completed_at = completed_at
            if processing_time_seconds is not None:
                event.processing_time_seconds = processing_time_seconds
            if error_message is not None:
                event.error_message = error_message
            if operation_details is not None:
                event.operation_details = operation_details

            self.session.flush()
        except Exception as e:
            self._handle_error("update_event_status", e)

    def get_events_by_entity(
        self,
        file_entity_id: int,
        event_type: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[FileProcessingEvent]:
        """
        Get events for a file entity.

        Args:
            file_entity_id: ID of the file entity
            event_type: Optional event type filter
            limit: Optional limit on number of results

        Returns:
            List of FileProcessingEvent instances
        """
        try:
            query = self.session.query(FileProcessingEvent).filter(
                FileProcessingEvent.file_entity_id == file_entity_id
            )

            if event_type:
                query = query.filter(FileProcessingEvent.event_type == event_type)

            query = query.order_by(FileProcessingEvent.created_at.desc())

            if limit:
                query = query.limit(limit)

            return query.all()
        except Exception as e:
            self._handle_error("get_events_by_entity", e)


class FileHistoryRepository(BaseRepository):
    """
    Repository for querying file history and lineage.

    Provides high-level queries for file tracking operations.
    """

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
        try:
            entity = (
                self.session.query(FileEntity)
                .filter(FileEntity.id == file_entity_id)
                .first()
            )

            if not entity:
                return {}

            result = {"entity": entity, "artifacts": [], "events": []}

            if include_artifacts:
                result["artifacts"] = (
                    self.session.query(FileArtifact)
                    .filter(FileArtifact.file_entity_id == file_entity_id)
                    .order_by(FileArtifact.created_at.desc())
                    .all()
                )

            if include_events:
                result["events"] = (
                    self.session.query(FileProcessingEvent)
                    .filter(FileProcessingEvent.file_entity_id == file_entity_id)
                    .order_by(FileProcessingEvent.created_at.desc())
                    .all()
                )

            return result
        except Exception as e:
            self._handle_error("get_file_history", e)

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
        try:
            query = self.session.query(FileArtifact).filter(
                and_(
                    FileArtifact.file_entity_id == file_entity_id,
                    FileArtifact.is_current == True,
                )
            )

            if role:
                query = query.filter(FileArtifact.role == role)

            return query.all()
        except Exception as e:
            self._handle_error("get_current_artifacts", e)
