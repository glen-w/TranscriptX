"""
Query utilities for transcript segments.

This module provides helper functions for common segment queries,
making it easy to retrieve segments by file, speaker, time range, or text search.
"""

from typing import List, Optional

from transcriptx.core.utils.logger import get_logger
from transcriptx.database import get_session
from transcriptx.database.repositories import (
    TranscriptFileRepository,
    TranscriptSegmentRepository,
    SpeakerRepository,
)
from transcriptx.database.models import TranscriptSegment, TranscriptFile

logger = get_logger()


def get_segments_for_file(file_path: str) -> List[TranscriptSegment]:
    """
    Get all segments for a transcript file.

    Args:
        file_path: Path to the transcript file

    Returns:
        List of TranscriptSegment instances, ordered by segment_index
    """
    try:
        session = get_session()
        file_repo = TranscriptFileRepository(session)
        segment_repo = TranscriptSegmentRepository(session)

        # Find file by path
        transcript_file = file_repo.get_transcript_file_by_path(file_path)
        if not transcript_file:
            logger.warning(f"⚠️ Transcript file not found: {file_path}")
            return []

        # Get segments
        segments = segment_repo.get_segments_by_file(
            transcript_file.id, order_by_index=True
        )

        return segments

    except Exception as e:
        logger.error(f"❌ Failed to get segments for file {file_path}: {e}")
        return []


def get_segments_for_speaker(
    speaker_name: str, limit: Optional[int] = None
) -> List[TranscriptSegment]:
    """
    Get all segments for a speaker.

    Args:
        speaker_name: Name of the speaker
        limit: Optional limit on number of results

    Returns:
        List of TranscriptSegment instances, ordered by creation date (newest first)
    """
    try:
        session = get_session()
        speaker_repo = SpeakerRepository(session)
        segment_repo = TranscriptSegmentRepository(session)

        # Find speaker by name
        speaker = speaker_repo.get_speaker_by_name(speaker_name)
        if not speaker:
            logger.warning(f"⚠️ Speaker not found: {speaker_name}")
            return []

        # Get segments
        segments = segment_repo.get_segments_by_speaker(speaker.id, limit=limit)

        return segments

    except Exception as e:
        logger.error(f"❌ Failed to get segments for speaker {speaker_name}: {e}")
        return []


def search_segments_by_text(
    query_text: str, file_path: Optional[str] = None, limit: Optional[int] = None
) -> List[TranscriptSegment]:
    """
    Search segments by text content.

    Args:
        query_text: Text to search for (case-insensitive)
        file_path: Optional file path to limit search to specific file
        limit: Optional limit on number of results

    Returns:
        List of TranscriptSegment instances matching the text
    """
    try:
        session = get_session()
        segment_repo = TranscriptSegmentRepository(session)

        # Get file ID if file_path is provided
        transcript_file_id = None
        if file_path:
            file_repo = TranscriptFileRepository(session)
            transcript_file = file_repo.get_transcript_file_by_path(file_path)
            if transcript_file:
                transcript_file_id = transcript_file.id
            else:
                logger.warning(f"⚠️ Transcript file not found: {file_path}")
                return []

        # Search segments
        segments = segment_repo.search_segments_by_text(
            query_text=query_text, transcript_file_id=transcript_file_id, limit=limit
        )

        return segments

    except Exception as e:
        logger.error(f"❌ Failed to search segments by text '{query_text}': {e}")
        return []


def get_segments_in_time_range(
    file_path: str, start_time: float, end_time: float
) -> List[TranscriptSegment]:
    """
    Get segments within a time range for a specific file.

    Args:
        file_path: Path to the transcript file
        start_time: Start of time range in seconds (inclusive)
        end_time: End of time range in seconds (inclusive)

    Returns:
        List of TranscriptSegment instances within the time range
    """
    try:
        session = get_session()
        file_repo = TranscriptFileRepository(session)
        segment_repo = TranscriptSegmentRepository(session)

        # Find file by path
        transcript_file = file_repo.get_transcript_file_by_path(file_path)
        if not transcript_file:
            logger.warning(f"⚠️ Transcript file not found: {file_path}")
            return []

        # Get segments in time range
        segments = segment_repo.get_segments_by_time_range(
            transcript_file_id=transcript_file.id,
            start_time=start_time,
            end_time=end_time,
        )

        return segments

    except Exception as e:
        logger.error(f"❌ Failed to get segments in time range for {file_path}: {e}")
        return []


def get_transcript_file_by_path(file_path: str) -> Optional[TranscriptFile]:
    """
    Get transcript file record by file path.

    Args:
        file_path: Path to the transcript file

    Returns:
        TranscriptFile instance or None if not found
    """
    try:
        session = get_session()
        file_repo = TranscriptFileRepository(session)
        return file_repo.get_transcript_file_by_path(file_path)

    except Exception as e:
        logger.error(f"❌ Failed to get transcript file {file_path}: {e}")
        return None
