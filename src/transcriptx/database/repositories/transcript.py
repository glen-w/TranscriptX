"""
Repository classes for TranscriptX database operations.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_

from transcriptx.core.utils.logger import get_logger
from ..models import TranscriptFile, TranscriptSegment, TranscriptSpeaker

logger = get_logger()


from .base import BaseRepository


class TranscriptFileRepository(BaseRepository):
    """
    Repository for transcript file-related database operations.

    This repository provides methods for:
    - Creating and retrieving transcript file records
    - Finding files by path or name
    - Managing file metadata
    """

    def create_or_get_transcript_file(
        self,
        file_path: str,
        file_name: Optional[str] = None,
        audio_file_path: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        segment_count: int = 0,
        speaker_count: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
        transcript_uuid: Optional[str] = None,
    ) -> TranscriptFile:
        """
        Create or retrieve a transcript file record.

        Args:
            file_path: Full path to transcript JSON file
            file_name: Base filename (extracted from path if not provided)
            audio_file_path: Original audio file path
            duration_seconds: Total duration in seconds
            segment_count: Number of segments
            speaker_count: Number of unique speakers
            metadata: Additional metadata dictionary
            transcript_uuid: Optional transcript UUID to persist

        Returns:
            TranscriptFile instance (existing or newly created)
        """
        try:
            # Check if file already exists (UUID-first)
            if transcript_uuid:
                existing_uuid = self.get_transcript_file_by_uuid(transcript_uuid)
                if existing_uuid:
                    logger.debug(
                        f"Found existing transcript file by UUID: {existing_uuid.id}"
                    )
                    return existing_uuid

            # Check if file already exists by path
            existing = self.get_transcript_file_by_path(file_path)
            if existing:
                logger.debug(f"Found existing transcript file: {existing.id}")
                return existing

            # Extract file name if not provided
            if not file_name:
                from pathlib import Path

                file_name = Path(file_path).name

            # Create new file record
            transcript_file = TranscriptFile(
                file_path=file_path,
                file_name=file_name,
                audio_file_path=audio_file_path,
                duration_seconds=duration_seconds,
                segment_count=segment_count,
                speaker_count=speaker_count,
                file_metadata=metadata or {},
                uuid=transcript_uuid if transcript_uuid else None,
            )

            self.session.add(transcript_file)
            self.session.commit()

            logger.info(f"✅ Created transcript file record: {file_name}")
            return transcript_file

        except Exception as e:
            self.session.rollback()
            self._handle_error("create_or_get_transcript_file", e)

    def get_transcript_file_by_path(self, file_path: str) -> Optional[TranscriptFile]:
        """Get transcript file by file path."""
        try:
            return (
                self.session.query(TranscriptFile)
                .filter(TranscriptFile.file_path == file_path)
                .first()
            )
        except Exception as e:
            self._handle_error("get_transcript_file_by_path", e)

    def get_transcript_file_by_id(self, file_id: int) -> Optional[TranscriptFile]:
        """Get transcript file by ID."""
        try:
            return (
                self.session.query(TranscriptFile)
                .filter(TranscriptFile.id == file_id)
                .first()
            )
        except Exception as e:
            self._handle_error("get_transcript_file_by_id", e)

    def get_transcript_file_by_uuid(self, file_uuid: str) -> Optional[TranscriptFile]:
        """Get transcript file by UUID."""
        try:
            return (
                self.session.query(TranscriptFile)
                .filter(TranscriptFile.uuid == file_uuid)
                .first()
            )
        except Exception as e:
            self._handle_error("get_transcript_file_by_uuid", e)

    def update_transcript_file(
        self, file_id: int, **kwargs
    ) -> Optional[TranscriptFile]:
        """
        Update transcript file information.

        Args:
            file_id: File ID to update
            **kwargs: Fields to update

        Returns:
            Updated TranscriptFile instance or None if not found
        """
        try:
            transcript_file = self.get_transcript_file_by_id(file_id)
            if not transcript_file:
                return None

            for key, value in kwargs.items():
                if hasattr(transcript_file, key):
                    setattr(transcript_file, key, value)

            transcript_file.updated_at = datetime.utcnow()
            self.session.commit()

            logger.info(f"✅ Updated transcript file: {transcript_file.file_name}")
            return transcript_file

        except Exception as e:
            self.session.rollback()
            self._handle_error("update_transcript_file", e)

    def update_transcript_file_path(
        self, file_uuid: str, new_file_path: str, new_file_name: Optional[str] = None
    ) -> Optional[TranscriptFile]:
        """
        Update transcript file path and name by UUID.

        Args:
            file_uuid: UUID of the transcript file to update
            new_file_path: New file path
            new_file_name: New file name (extracted from path if not provided)

        Returns:
            Updated TranscriptFile instance or None if not found
        """
        try:
            transcript_file = self.get_transcript_file_by_uuid(file_uuid)
            if not transcript_file:
                return None

            transcript_file.file_path = new_file_path
            if new_file_name:
                transcript_file.file_name = new_file_name
            else:
                from pathlib import Path

                transcript_file.file_name = Path(new_file_path).name

            transcript_file.updated_at = datetime.utcnow()
            self.session.commit()

            logger.info(f"✅ Updated transcript file path: {transcript_file.file_name}")
            return transcript_file

        except Exception as e:
            self.session.rollback()
            self._handle_error("update_transcript_file_path", e)


class TranscriptSegmentRepository(BaseRepository):
    """
    Repository for transcript segment-related database operations.

    This repository provides methods for:
    - Creating individual segments
    - Bulk creating segments
    - Querying segments by various criteria
    - Time-based and speaker-based queries
    """

    def create_segment(
        self,
        transcript_file_id: int,
        segment_index: int,
        text: str,
        start_time: float,
        end_time: float,
        speaker_id: Optional[int] = None,
        word_count: Optional[int] = None,
    ) -> TranscriptSegment:
        """
        Create a single transcript segment.

        Args:
            transcript_file_id: ID of the transcript file
            segment_index: Order of segment in transcript (0-based)
            text: Segment text content
            start_time: Start timestamp in seconds
            end_time: End timestamp in seconds
            speaker_id: ID of the speaker (optional)
            word_count: Number of words (calculated if not provided)

        Returns:
            Created TranscriptSegment instance
        """
        try:
            # Calculate duration
            duration = end_time - start_time

            # Calculate word count if not provided
            if word_count is None:
                word_count = len(text.split())

            segment = TranscriptSegment(
                transcript_file_id=transcript_file_id,
                segment_index=segment_index,
                text=text,
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                speaker_id=speaker_id,
                word_count=word_count,
            )

            self.session.add(segment)
            self.session.commit()

            return segment

        except Exception as e:
            self.session.rollback()
            self._handle_error("create_segment", e)

    def bulk_create_segments(
        self, segments_data: List[Dict[str, Any]]
    ) -> List[TranscriptSegment]:
        """
        Bulk create transcript segments.

        Args:
            segments_data: List of segment dictionaries with keys:
                - transcript_file_id (required)
                - segment_index (required)
                - text (required)
                - start_time (required)
                - end_time (required)
                - speaker_id (optional)
                - word_count (optional)

        Returns:
            List of created TranscriptSegment instances
        """
        try:
            segments = []
            for seg_data in segments_data:
                # Calculate duration
                duration = seg_data["end_time"] - seg_data["start_time"]

                # Calculate word count if not provided
                word_count = seg_data.get("word_count")
                if word_count is None:
                    word_count = len(seg_data["text"].split())

                segment = TranscriptSegment(
                    transcript_file_id=seg_data["transcript_file_id"],
                    segment_index=seg_data["segment_index"],
                    text=seg_data["text"],
                    start_time=seg_data["start_time"],
                    end_time=seg_data["end_time"],
                    duration=duration,
                    speaker_id=seg_data.get("speaker_id"),
                    word_count=word_count,
                )
                segments.append(segment)

            # Use add_all instead of bulk_save_objects to get IDs
            self.session.add_all(segments)
            self.session.flush()  # Flush to get IDs without committing

            # IDs are now available
            self.session.commit()

            logger.info(f"✅ Bulk created {len(segments)} transcript segments")
            return segments

        except Exception as e:
            self.session.rollback()
            self._handle_error("bulk_create_segments", e)

    def get_segments_by_file(
        self, transcript_file_id: int, order_by_index: bool = True
    ) -> List[TranscriptSegment]:
        """
        Get all segments for a transcript file.

        Args:
            transcript_file_id: ID of the transcript file
            order_by_index: If True, order by segment_index

        Returns:
            List of TranscriptSegment instances
        """
        try:
            query = self.session.query(TranscriptSegment).filter(
                TranscriptSegment.transcript_file_id == transcript_file_id
            )

            if order_by_index:
                query = query.order_by(TranscriptSegment.segment_index)

            return query.all()

        except Exception as e:
            self._handle_error("get_segments_by_file", e)

    def get_segments_by_speaker(
        self, speaker_id: int, limit: Optional[int] = None
    ) -> List[TranscriptSegment]:
        """
        Get all segments for a speaker.

        Args:
            speaker_id: ID of the speaker
            limit: Optional limit on number of results

        Returns:
            List of TranscriptSegment instances
        """
        try:
            query = (
                self.session.query(TranscriptSegment)
                .filter(TranscriptSegment.speaker_id == speaker_id)
                .order_by(TranscriptSegment.created_at.desc())
            )

            if limit:
                query = query.limit(limit)

            return query.all()

        except Exception as e:
            self._handle_error("get_segments_by_speaker", e)

    def get_segments_by_time_range(
        self, transcript_file_id: int, start_time: float, end_time: float
    ) -> List[TranscriptSegment]:
        """
        Get segments within a time range.

        Args:
            transcript_file_id: ID of the transcript file
            start_time: Start of time range (inclusive)
            end_time: End of time range (inclusive)

        Returns:
            List of TranscriptSegment instances within the time range
        """
        try:
            return (
                self.session.query(TranscriptSegment)
                .filter(
                    and_(
                        TranscriptSegment.transcript_file_id == transcript_file_id,
                        TranscriptSegment.start_time >= start_time,
                        TranscriptSegment.end_time <= end_time,
                    )
                )
                .order_by(TranscriptSegment.start_time)
                .all()
            )

        except Exception as e:
            self._handle_error("get_segments_by_time_range", e)

    def search_segments_by_text(
        self,
        query_text: str,
        transcript_file_id: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[TranscriptSegment]:
        """
        Search segments by text content.

        Args:
            query_text: Text to search for
            transcript_file_id: Optional file ID to limit search
            limit: Optional limit on number of results

        Returns:
            List of TranscriptSegment instances matching the text
        """
        try:
            query = self.session.query(TranscriptSegment).filter(
                TranscriptSegment.text.ilike(f"%{query_text}%")
            )

            if transcript_file_id:
                query = query.filter(
                    TranscriptSegment.transcript_file_id == transcript_file_id
                )

            query = query.order_by(TranscriptSegment.created_at.desc())

            if limit:
                query = query.limit(limit)

            return query.all()

        except Exception as e:
            self._handle_error("search_segments_by_text", e)


class TranscriptSpeakerRepository(BaseRepository):
    """Repository for transcript-scoped speakers."""

    def get_by_label(
        self, transcript_file_id: int, speaker_label: str
    ) -> Optional[TranscriptSpeaker]:
        try:
            return (
                self.session.query(TranscriptSpeaker)
                .filter(
                    TranscriptSpeaker.transcript_file_id == transcript_file_id,
                    TranscriptSpeaker.speaker_label == speaker_label,
                )
                .first()
            )
        except Exception as e:
            self._handle_error("get_by_label", e)

    def create_transcript_speaker(
        self,
        transcript_file_id: int,
        speaker_label: str,
        speaker_order: Optional[int] = None,
        display_name: Optional[str] = None,
        speaker_fingerprint: Optional[str] = None,
    ) -> TranscriptSpeaker:
        try:
            speaker = TranscriptSpeaker(
                transcript_file_id=transcript_file_id,
                speaker_label=speaker_label,
                speaker_order=speaker_order,
                display_name=display_name,
                speaker_fingerprint=speaker_fingerprint,
            )
            self.session.add(speaker)
            self.session.flush()
            return speaker
        except Exception as e:
            self._handle_error("create_transcript_speaker", e)
