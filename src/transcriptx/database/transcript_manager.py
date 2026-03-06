"""
Transcript Manager for TranscriptX Database Integration.

This module provides a comprehensive interface for managing transcript data
in the database, including conversation creation, speaker management,
analysis result storage, and cross-session tracking.

Key Features:
- Automatic conversation creation from transcript files
- Speaker profile management and tracking
- Analysis result storage and retrieval
- Cross-session speaker identification
- Transcript metadata management
- Batch processing support

The TranscriptManager integrates with the existing analysis pipeline
to provide persistent storage of transcript data and analysis results.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from transcriptx.core.utils.logger import get_logger
from transcriptx.database import get_session
from transcriptx.database.repositories import (
    SpeakerRepository,
    ConversationRepository,
    AnalysisRepository,
    ProfileRepository,
)
from transcriptx.database.speaker_profiling import SpeakerProfilingService
from transcriptx.database.cross_session_tracking import CrossSessionTrackingService
from transcriptx.database.speaker_statistics import SpeakerStatisticsService

logger = get_logger()


class TranscriptManager:
    """
    Manager for transcript database operations.

    This class provides a unified interface for storing and managing
    transcript data in the database, including conversations, speakers,
    sessions, and analysis results.
    """

    def __init__(self):
        """Initialize the transcript manager."""
        self.session = get_session()
        self.speaker_repo = SpeakerRepository(self.session)
        self.conversation_repo = ConversationRepository(self.session)
        self.analysis_repo = AnalysisRepository(self.session)
        self.profile_repo = ProfileRepository(self.session)
        self.speaker_profiling = SpeakerProfilingService()
        self.cross_session_tracking = CrossSessionTrackingService()
        self.speaker_statistics = SpeakerStatisticsService()

    def store_transcript(
        self,
        transcript_path: str,
        analysis_config: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Any, List[Any]]:
        """
        Store a transcript in the database.

        Args:
            transcript_path: Path to the transcript JSON file
            analysis_config: Analysis configuration used
            metadata: Additional metadata

        Returns:
            Tuple of (conversation, speakers) where conversation is the created
            conversation instance and speakers is a list of speaker instances
        """
        try:
            logger.info(f"🔧 Storing transcript in database: {transcript_path}")

            # Load transcript data
            with open(transcript_path, "r", encoding="utf-8") as f:
                transcript_data = json.load(f)

            # Extract basic information
            segments = transcript_data.get("segments", [])
            if not segments:
                raise ValueError("No segments found in transcript data")

            # Calculate metadata
            duration_seconds = (
                max(seg.get("end", 0) for seg in segments) if segments else 0
            )
            word_count = sum(len(seg.get("text", "").split()) for seg in segments)
            speaker_ids = list(
                set(seg.get("speaker") for seg in segments if seg.get("speaker"))
            )
            speaker_count = len(speaker_ids)

            # Create conversation
            base_name = Path(transcript_path).stem
            conversation = self.conversation_repo.create_conversation(
                title=f"Conversation: {base_name}",
                description=f"Transcript analysis for {base_name}",
                meeting_id=base_name,
                transcript_file_path=transcript_path,
                duration_seconds=duration_seconds,
                word_count=word_count,
                speaker_count=speaker_count,
                analysis_config=analysis_config or {},
                conversation_date=datetime.now(),
            )

            # Store speakers and sessions
            # Speaker names come directly from segments
            speakers = []
            for speaker_id in speaker_ids:
                # Get speaker name from segments (speaker field contains the name)
                speaker_segments = [
                    seg for seg in segments if seg.get("speaker") == speaker_id
                ]
                speaker_name = (
                    speaker_segments[0].get("speaker", f"Speaker_{speaker_id}")
                    if speaker_segments
                    else f"Speaker_{speaker_id}"
                )

                # Get segments for this speaker
                speaker_segments = [
                    seg for seg in segments if seg.get("speaker") == speaker_id
                ]

                # Try to find existing speaker using cross-session tracking
                matched_speaker = None
                match_confidence = 0.0
                is_new = False

                # Only try cross-session matching if we have a real name (not generic ID)
                if speaker_name and not speaker_name.startswith("Speaker_"):
                    try:
                        matches = self.cross_session_tracking.find_speaker_matches(
                            speaker_name=speaker_name,
                            session_data=speaker_segments,
                            confidence_threshold=0.6,
                        )

                        if matches:
                            # Use the best match
                            matched_speaker, match_confidence = matches[0]
                            logger.info(
                                f"🔗 Found cross-session match for '{speaker_name}': {matched_speaker.name} (confidence: {match_confidence:.2f})"
                            )
                    except Exception as e:
                        logger.debug(
                            f"Cross-session matching failed for {speaker_name}: {e}"
                        )

                # Use matched speaker or create/get new one
                if matched_speaker and match_confidence >= 0.7:
                    speaker = matched_speaker
                    is_new = False
                    # Update speaker with new information if needed
                    if speaker_name != speaker.name:
                        # Update display name if we have a better one
                        if (
                            not speaker.display_name
                            or speaker.display_name == speaker.name
                        ):
                            speaker.display_name = speaker_name
                    # Update confidence score
                    if (
                        not speaker.confidence_score
                        or match_confidence > speaker.confidence_score
                    ):
                        speaker.confidence_score = match_confidence
                    self.session.commit()
                else:
                    # Create or get speaker
                    speaker, is_new = self.speaker_profiling.create_or_get_speaker(
                        name=speaker_name, display_name=speaker_name
                    )

                    # Set canonical_id for cross-session tracking if we have a real name
                    if (
                        is_new
                        and speaker_name
                        and not speaker_name.startswith("Speaker_")
                    ):
                        speaker.canonical_id = speaker_name.lower().strip()
                        speaker.confidence_score = 1.0
                        self.session.commit()

                speakers.append(speaker)

                # Create session for this speaker
                session = self._create_speaker_session(
                    conversation, speaker, speaker_segments
                )

                # Create or update speaker profile
                try:
                    # If we matched an existing speaker or this is not a new speaker, update profile
                    if matched_speaker or not is_new:
                        # Update existing profile
                        self.speaker_profiling.update_speaker_profile(
                            speaker_id=speaker.id, segments_data=speaker_segments
                        )
                    else:
                        # Create new profile
                        self.speaker_profiling.create_speaker_profile(
                            speaker_id=speaker.id, segments_data=speaker_segments
                        )
                except Exception as e:
                    logger.warning(
                        f"⚠️ Failed to create/update speaker profile for {speaker.name}: {e}"
                    )

                # Update speaker statistics
                try:
                    # Get analysis results if available (would need to be passed in)
                    analysis_results = (
                        metadata.get("analysis_results") if metadata else None
                    )
                    self.speaker_statistics.update_speaker_statistics(
                        speaker_id=speaker.id,
                        conversation_id=conversation.id,
                        segments_data=speaker_segments,
                        analysis_results=analysis_results,
                    )
                except Exception as e:
                    logger.warning(
                        f"⚠️ Failed to update speaker statistics for {speaker.name}: {e}"
                    )

                # Track speaker evolution if this is not a new speaker
                if matched_speaker or not is_new:
                    try:
                        self.cross_session_tracking.track_speaker_evolution(
                            speaker_id=speaker.id,
                            session_data=speaker_segments,
                            session_id=session.id,
                        )
                    except Exception as e:
                        logger.debug(f"Failed to track speaker evolution: {e}")

            # Add conversation metadata
            if metadata:
                for key, value in metadata.items():
                    self.conversation_repo.add_conversation_metadata(
                        conversation_id=conversation.id,
                        key=key,
                        value=str(value),
                        value_type="string",
                    )

            logger.info(f"✅ Stored transcript in database: {conversation.title}")
            return conversation, speakers

        except Exception as e:
            logger.error(f"❌ Failed to store transcript {transcript_path}: {e}")
            raise

    def _create_speaker_session(
        self, conversation: Any, speaker: Any, segments: List[Dict[str, Any]]
    ) -> Any:
        """Create a session for a speaker in a conversation."""
        try:
            # Calculate session metrics
            speaking_time = sum(
                seg.get("end", 0) - seg.get("start", 0) for seg in segments
            )
            word_count = sum(len(seg.get("text", "").split()) for seg in segments)
            segment_count = len(segments)

            # Calculate speaking rate (words per minute)
            speaking_rate = (
                (word_count / (speaking_time / 60)) if speaking_time > 0 else 0
            )

            # Find longest and shortest segments
            segment_durations = [
                seg.get("end", 0) - seg.get("start", 0) for seg in segments
            ]
            longest_segment = max(segment_durations) if segment_durations else 0
            shortest_segment = min(segment_durations) if segment_durations else 0

            # Create session
            from transcriptx.database.models import Session as DBSession

            session = DBSession(
                speaker_id=speaker.id,
                conversation_id=conversation.id,
                segments_data=segments,
                speaking_time_seconds=speaking_time,
                word_count=word_count,
                segment_count=segment_count,
                average_speaking_rate=speaking_rate,
                longest_segment_seconds=longest_segment,
                shortest_segment_seconds=shortest_segment,
            )

            self.session.add(session)
            self.session.commit()

            logger.info(
                f"✅ Created session for speaker {speaker.name} in conversation {conversation.title}"
            )
            return session

        except Exception as e:
            self.session.rollback()
            logger.error(f"❌ Failed to create session for speaker {speaker.name}: {e}")
            raise

    def store_analysis_result(
        self,
        conversation_id: int,
        analysis_type: str,
        results_data: Dict[str, Any],
        summary_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        processing_time: Optional[float] = None,
    ) -> Any:
        """
        Store analysis results in the database.

        Args:
            conversation_id: ID of the conversation
            analysis_type: Type of analysis (sentiment, emotion, etc.)
            results_data: Complete analysis results
            summary_data: Summary statistics
            metadata: Additional metadata
            processing_time: Processing time in seconds

        Returns:
            Created analysis result instance
        """
        try:
            analysis_result = self.analysis_repo.create_analysis_result(
                conversation_id=conversation_id,
                analysis_type=analysis_type,
                results_data=results_data,
                summary_data=summary_data or {},
                metadata=metadata or {},
                processing_time_seconds=processing_time,
            )

            logger.info(
                f"✅ Stored {analysis_type} analysis result for conversation {conversation_id}"
            )
            return analysis_result

        except Exception as e:
            logger.error(f"❌ Failed to store {analysis_type} analysis result: {e}")
            raise

    def get_conversation_by_transcript_path(
        self, transcript_path: str
    ) -> Optional[Any]:
        """Get conversation by transcript file path."""
        try:
            return self.conversation_repo.find_conversation_by_transcript_path(
                transcript_path
            )
        except Exception as e:
            logger.error(f"❌ Failed to get conversation by transcript path: {e}")
            return None

    def get_speakers_for_conversation(self, conversation_id: int) -> List[Any]:
        """Get all speakers for a conversation."""
        try:
            conversation = self.conversation_repo.get_conversation_by_id(
                conversation_id
            )
            if not conversation:
                return []

            speakers = []
            for session in conversation.sessions:
                speakers.append(session.speaker)

            return speakers

        except Exception as e:
            logger.error(
                f"❌ Failed to get speakers for conversation {conversation_id}: {e}"
            )
            return []

    def update_conversation_analysis_status(
        self, conversation_id: int, status: str, error_message: Optional[str] = None
    ) -> None:
        """Update the analysis status of a conversation."""
        try:
            conversation = self.conversation_repo.get_conversation_by_id(
                conversation_id
            )
            if conversation:
                conversation.analysis_status = status
                if error_message:
                    conversation.analysis_config["error_message"] = error_message
                self.session.commit()
                logger.info(
                    f"✅ Updated conversation {conversation_id} status to {status}"
                )

        except Exception as e:
            self.session.rollback()
            logger.error(f"❌ Failed to update conversation status: {e}")
            raise

    def get_conversation_summary(self, conversation_id: int) -> Dict[str, Any]:
        """Get a comprehensive summary of a conversation."""
        try:
            conversation = self.conversation_repo.get_conversation_by_id(
                conversation_id
            )
            if not conversation:
                return {}

            # Get speakers
            speakers = self.get_speakers_for_conversation(conversation_id)

            # Get analysis results
            analysis_results = self.analysis_repo.get_analysis_results_by_conversation(
                conversation_id
            )

            # Get metadata
            metadata = self.conversation_repo.get_conversation_metadata(conversation_id)

            return {
                "conversation": {
                    "id": conversation.id,
                    "title": conversation.title,
                    "description": conversation.description,
                    "duration_seconds": conversation.duration_seconds,
                    "word_count": conversation.word_count,
                    "speaker_count": conversation.speaker_count,
                    "analysis_status": conversation.analysis_status,
                    "created_at": conversation.created_at.isoformat(),
                    "updated_at": conversation.updated_at.isoformat(),
                },
                "speakers": [
                    {
                        "id": speaker.id,
                        "name": speaker.name,
                        "display_name": speaker.display_name,
                        "organization": speaker.organization,
                        "role": speaker.role,
                    }
                    for speaker in speakers
                ],
                "analysis_results": [
                    {
                        "id": result.id,
                        "analysis_type": result.analysis_type,
                        "status": result.status,
                        "processing_time_seconds": result.processing_time_seconds,
                        "created_at": result.created_at.isoformat(),
                    }
                    for result in analysis_results
                ],
                "metadata": [
                    {"key": meta.key, "value": meta.value, "category": meta.category}
                    for meta in metadata
                ],
            }

        except Exception as e:
            logger.error(f"❌ Failed to get conversation summary: {e}")
            return {}

    def list_conversations(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        status_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List conversations with optional filtering."""
        try:
            conversations = self.conversation_repo.find_conversations(
                limit=limit, offset=offset, status=status_filter
            )

            return [
                {
                    "id": conv.id,
                    "title": conv.title,
                    "description": conv.description,
                    "duration_seconds": conv.duration_seconds,
                    "speaker_count": conv.speaker_count,
                    "analysis_status": conv.analysis_status,
                    "created_at": conv.created_at.isoformat(),
                    "updated_at": conv.updated_at.isoformat(),
                }
                for conv in conversations
            ]

        except Exception as e:
            logger.error(f"❌ Failed to list conversations: {e}")
            return []

    def delete_conversation(self, conversation_id: int) -> bool:
        """Delete a conversation and all associated data."""
        try:
            # Delete analysis results first
            analysis_results = self.analysis_repo.get_analysis_results_by_conversation(
                conversation_id
            )
            for result in analysis_results:
                self.session.delete(result)

            # Delete sessions
            conversation = self.conversation_repo.get_conversation_by_id(
                conversation_id
            )
            if conversation:
                for session in conversation.sessions:
                    self.session.delete(session)

            # Delete conversation metadata
            metadata = self.conversation_repo.get_conversation_metadata(conversation_id)
            for meta in metadata:
                self.session.delete(meta)

            # Delete conversation
            if conversation:
                self.session.delete(conversation)

            self.session.commit()
            logger.info(f"✅ Deleted conversation {conversation_id}")
            return True

        except Exception as e:
            self.session.rollback()
            logger.error(f"❌ Failed to delete conversation {conversation_id}: {e}")
            return False

    def close(self):
        """Close the database session."""
        if self.session:
            self.session.close()
