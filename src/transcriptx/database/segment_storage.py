"""
Segment Storage Service for TranscriptX Database Integration.

This module provides a service class for storing transcript segments
in the database, handling file creation, speaker mapping, and bulk segment insertion.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from transcriptx.core.utils.logger import get_logger
from transcriptx.database.database import get_session
from transcriptx.database.repositories import (
    TranscriptFileRepository,
    TranscriptSegmentRepository,
    SpeakerRepository,
)
from transcriptx.database.models import TranscriptFile, TranscriptSegment
from transcriptx.database.sentence_storage import SentenceStorageService
from transcriptx.database.vocabulary_storage import VocabularyStorageService
from transcriptx.database.speaker_profiling import SpeakerIdentityService

logger = get_logger()


class SegmentStorageService:
    """
    Service for storing transcript segments in the database.

    This service handles:
    - Loading transcript JSON files
    - Creating or retrieving transcript file records
    - Mapping speakers and creating speaker records
    - Bulk storing segments
    """

    def __init__(self):
        """Initialize the segment storage service."""
        self.session = get_session()
        self.file_repo = TranscriptFileRepository(self.session)
        self.segment_repo = TranscriptSegmentRepository(self.session)
        self.speaker_repo = SpeakerRepository(self.session)

    def store_transcript_segments(
        self,
        transcript_path: str,
        speaker_map: Optional[Dict[str, str]] = None,
        audio_file_path: Optional[str] = None,
        update_existing: bool = False,
    ) -> Tuple[TranscriptFile, List[TranscriptSegment]]:
        """
        Store all segments from a transcript file in the database.

        Args:
            transcript_path: Path to the transcript JSON file
            speaker_map: Dictionary mapping speaker IDs to names (e.g., {"SPEAKER_01": "Alice"})
            audio_file_path: Path to the original audio file (optional)
            update_existing: Update speaker_id for existing segments by index

        Returns:
            Tuple of (transcript_file, segments_list)

        Raises:
            FileNotFoundError: If transcript file doesn't exist
            ValueError: If transcript file is invalid
            Exception: For database errors
        """
        try:
            logger.info(f"🔧 Storing transcript segments: {transcript_path}")

            # Load transcript data
            transcript_path_obj = Path(transcript_path)
            if not transcript_path_obj.exists():
                raise FileNotFoundError(f"Transcript file not found: {transcript_path}")

            with open(transcript_path, "r", encoding="utf-8") as f:
                transcript_data = json.load(f)

            # Extract segments
            segments = transcript_data.get("segments", [])
            if not segments:
                raise ValueError("No segments found in transcript data")

            # Metadata & identity
            file_metadata: Dict[str, Any] = {}
            metadata = transcript_data.get("metadata")
            if isinstance(metadata, dict):
                file_metadata.update(metadata)
            transcript_uuid = file_metadata.get("transcript_uuid") or transcript_data.get(
                "transcript_uuid"
            )

            # Calculate metadata
            duration_seconds = (
                max(seg.get("end", 0) for seg in segments) if segments else 0
            )
            segment_count = len(segments)
            speaker_ids = list(
                set(seg.get("speaker") for seg in segments if seg.get("speaker"))
            )
            speaker_count = len(speaker_ids)

            # Create or get transcript file record (UUID-first)
            resolved_path = str(transcript_path_obj.resolve())
            file_metadata.update({"source": "whisperx", "speaker_ids": speaker_ids})

            transcript_file = None
            if transcript_uuid:
                transcript_file = self.file_repo.get_transcript_file_by_uuid(
                    str(transcript_uuid)
                )
                if transcript_file and transcript_file.file_path != resolved_path:
                    updated = self.file_repo.update_transcript_file_path(
                        file_uuid=transcript_file.uuid,
                        new_file_path=resolved_path,
                        new_file_name=transcript_path_obj.name,
                    )
                    if updated:
                        transcript_file.file_path = resolved_path
                        transcript_file.file_name = transcript_path_obj.name

            if not transcript_file:
                transcript_file = self.file_repo.create_or_get_transcript_file(
                    file_path=resolved_path,
                    file_name=transcript_path_obj.name,
                    audio_file_path=str(audio_file_path) if audio_file_path else None,
                    duration_seconds=duration_seconds,
                    segment_count=segment_count,
                    speaker_count=speaker_count,
                    metadata=file_metadata,
                    transcript_uuid=str(transcript_uuid) if transcript_uuid else None,
                )

            # Check if segments already exist for this file
            existing_segments = self.segment_repo.get_segments_by_file(
                transcript_file.id
            )
            if existing_segments:
                logger.info(
                    f"📋 Found {len(existing_segments)} existing segments for file {transcript_file.id}"
                )
                if not update_existing:
                    return transcript_file, existing_segments

                # Resolve speakers and update existing segments by segment_index
                identity_service = SpeakerIdentityService()
                speaker_id_map: Dict[str, int] = {}

                for diarized_label in speaker_ids:
                    speaker_segments = [
                        seg for seg in segments if seg.get("speaker") == diarized_label
                    ]
                    speaker, _, _ = identity_service.resolve_speaker_identity(
                        diarized_label=diarized_label,
                        transcript_file_id=transcript_file.id,
                        session_data=speaker_segments,
                        confidence_threshold=0.7,
                    )
                    speaker_id_map[diarized_label] = speaker.id

                segment_by_index = {
                    segment.segment_index: segment for segment in existing_segments
                }
                updated_count = 0
                for index, segment in enumerate(segments):
                    existing_segment = segment_by_index.get(index)
                    if not existing_segment:
                        continue
                    speaker_label = segment.get("speaker")
                    db_speaker_id = (
                        speaker_id_map.get(speaker_label) if speaker_label else None
                    )
                    if existing_segment.speaker_id != db_speaker_id:
                        existing_segment.speaker_id = db_speaker_id
                        updated_count += 1
                        for sentence in existing_segment.sentences:
                            if sentence.speaker_id != db_speaker_id:
                                sentence.speaker_id = db_speaker_id

                if updated_count:
                    self.session.commit()
                    logger.info(
                        f"✅ Updated speaker_id for {updated_count} existing segments"
                    )

                identity_service.close()
                return transcript_file, existing_segments

            # Use SpeakerIdentityService for canonical identity resolution
            identity_service = SpeakerIdentityService()

            # Create speaker ID to database ID mapping
            speaker_id_map: Dict[str, int] = {}
            speaker_texts_map: Dict[int, List[str]] = {}  # For vocabulary storage

            # Process each speaker ID using canonical identity resolution
            for diarized_label in speaker_ids:
                # Get speaker segments for this diarized label
                speaker_segments = [
                    seg for seg in segments if seg.get("speaker") == diarized_label
                ]

                # Resolve speaker identity using canonical service
                speaker, is_new, resolution_metadata = (
                    identity_service.resolve_speaker_identity(
                        diarized_label=diarized_label,
                        transcript_file_id=transcript_file.id,
                        session_data=speaker_segments,
                        confidence_threshold=0.7,
                    )
                )

                speaker_id_map[diarized_label] = speaker.id

                # Collect texts for vocabulary storage
                speaker_texts = [
                    seg.get("text", "") for seg in speaker_segments if seg.get("text")
                ]
                if speaker_texts:
                    speaker_texts_map[speaker.id] = speaker_texts

            # Prepare segments for bulk insert
            segments_data = []
            for index, segment in enumerate(segments):
                speaker_id = segment.get("speaker")
                db_speaker_id = speaker_id_map.get(speaker_id) if speaker_id else None

                segments_data.append(
                    {
                        "transcript_file_id": transcript_file.id,
                        "segment_index": index,
                        "text": segment.get("text", ""),
                        "start_time": segment.get("start", 0.0),
                        "end_time": segment.get("end", 0.0),
                        "speaker_id": db_speaker_id,
                        "word_count": len(segment.get("text", "").split()),
                    }
                )

            # Bulk create segments
            stored_segments = self.segment_repo.bulk_create_segments(segments_data)

            # Update transcript file with actual segment count
            self.file_repo.update_transcript_file(
                transcript_file.id, segment_count=len(stored_segments)
            )

            logger.info(
                f"✅ Stored {len(stored_segments)} segments for file {transcript_file.id}"
            )

            # Store sentences from segments
            sentence_service = SentenceStorageService()
            try:
                sentences = sentence_service.store_sentences_from_segments(
                    segments=stored_segments
                )
                logger.info(
                    f"✅ Stored {len(sentences)} sentences from {len(stored_segments)} segments"
                )
            except Exception as e:
                logger.warning(f"⚠️ Failed to store sentences: {e}")
            finally:
                sentence_service.close()

            # Store vocabulary snapshots for each speaker
            vocabulary_service = VocabularyStorageService()
            try:
                for speaker_id, texts in speaker_texts_map.items():
                    try:
                        vocabulary_service.store_speaker_vocabulary_snapshot(
                            speaker_id=speaker_id,
                            texts=texts,
                            transcript_file_id=transcript_file.id,
                            source_window="full_transcript",
                        )
                    except Exception as e:
                        logger.warning(
                            f"⚠️ Failed to store vocabulary for speaker {speaker_id}: {e}"
                        )
            finally:
                vocabulary_service.close()

            # Close identity service
            identity_service.close()

            return transcript_file, stored_segments

        except Exception as e:
            logger.error(f"❌ Failed to store transcript segments: {e}")
            if self.session:
                self.session.rollback()
            raise

    def close(self):
        """Close the database session."""
        if self.session:
            self.session.close()


def store_transcript_segments_from_json(
    transcript_path: str,
    audio_file_path: Optional[str] = None,
    update_existing: bool = False,
) -> Optional[Tuple[TranscriptFile, List[TranscriptSegment]]]:
    """
    Store transcript segments from a JSON file (no gating).

    Returns (transcript_file, segments) on success, or None on failure.
    """
    try:
        from transcriptx.database import init_database

        init_database()
        service = SegmentStorageService()
        try:
            transcript_file, segments = service.store_transcript_segments(
                transcript_path=transcript_path,
                audio_file_path=audio_file_path,
                update_existing=update_existing,
            )
            logger.info(
                f"✅ Stored {len(segments)} segments in database (file_id: {transcript_file.id})"
            )
            logger.info(
                f"✅ DB store complete: transcript_file_id={transcript_file.id}, segments={len(segments)}, speakers_resolved={transcript_file.speaker_count}"
            )
            return transcript_file, segments
        finally:
            service.close()
    except Exception as e:
        logger.warning(f"⚠️ Failed to store segments in database: {e}")
        return None
