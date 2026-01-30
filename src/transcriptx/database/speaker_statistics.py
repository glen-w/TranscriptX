"""
Speaker statistics service for TranscriptX database.

This module provides comprehensive speaker statistics tracking and aggregation
across multiple conversations and sessions.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from transcriptx.core.utils.logger import get_logger
from transcriptx.database import get_session
from transcriptx.database.models import SpeakerStats, Session, Conversation
from transcriptx.database.repositories import SpeakerRepository

logger = get_logger()


class SpeakerStatisticsService:
    """
    Service for tracking and aggregating speaker statistics.

    This service provides:
    - Aggregate statistics across all conversations
    - Trend analysis and pattern detection
    - Speaker performance metrics
    - Comparative analysis
    """

    def __init__(self):
        """Initialize the speaker statistics service."""
        self.session = get_session()
        self.speaker_repo = SpeakerRepository(self.session)

    def update_speaker_statistics(
        self,
        speaker_id: int,
        conversation_id: int,
        segments_data: List[Dict[str, Any]],
        analysis_results: Optional[Dict[str, Any]] = None,
    ) -> SpeakerStats:
        """
        Update speaker statistics for a conversation.

        Args:
            speaker_id: ID of the speaker
            conversation_id: ID of the conversation
            segments_data: List of speaker segments
            analysis_results: Optional analysis results

        Returns:
            Updated speaker statistics
        """
        try:
            # Calculate basic metrics
            total_speaking_time = sum(
                seg.get("end", 0) - seg.get("start", 0) for seg in segments_data
            )
            total_word_count = sum(
                len(seg.get("text", "").split()) for seg in segments_data
            )
            total_segment_count = len(segments_data)
            average_speaking_rate = (
                total_word_count / (total_speaking_time / 60)
                if total_speaking_time > 0
                else 0
            )

            # Extract sentiment and emotion from analysis results
            average_sentiment_score = None
            dominant_emotion = None
            emotion_distribution = {}

            if analysis_results:
                # Try to extract sentiment
                sentiment_data = analysis_results.get("sentiment", {})
                if isinstance(sentiment_data, dict):
                    speaker_sentiment = sentiment_data.get("speakers", {}).get(
                        str(speaker_id), {}
                    )
                    if speaker_sentiment:
                        average_sentiment_score = speaker_sentiment.get(
                            "average_sentiment"
                        )

                # Try to extract emotion
                emotion_data = analysis_results.get("emotion", {})
                if isinstance(emotion_data, dict):
                    speaker_emotion = emotion_data.get("speakers", {}).get(
                        str(speaker_id), {}
                    )
                    if speaker_emotion:
                        dominant_emotion = speaker_emotion.get("dominant_emotion")
                        emotion_distribution = speaker_emotion.get(
                            "emotion_distribution", {}
                        )

            # Get or create current stats
            current_stats = (
                self.session.query(SpeakerStats)
                .filter(
                    SpeakerStats.speaker_id == speaker_id,
                    SpeakerStats.is_current == True,
                    SpeakerStats.stats_period == "all_time",
                )
                .first()
            )

            if current_stats:
                # Update existing stats
                current_stats.total_speaking_time = (
                    current_stats.total_speaking_time or 0
                ) + total_speaking_time
                current_stats.total_word_count = (
                    current_stats.total_word_count or 0
                ) + total_word_count
                current_stats.total_segment_count = (
                    current_stats.total_segment_count or 0
                ) + total_segment_count

                # Recalculate average speaking rate
                if (
                    current_stats.total_speaking_time
                    and current_stats.total_speaking_time > 0
                ):
                    current_stats.average_speaking_rate = (
                        current_stats.total_word_count
                        / (current_stats.total_speaking_time / 60)
                    )

                # Update sentiment and emotion if available
                if average_sentiment_score is not None:
                    # Weighted average with existing sentiment
                    if current_stats.average_sentiment_score is not None:
                        # Simple average for now
                        current_stats.average_sentiment_score = (
                            current_stats.average_sentiment_score
                            + average_sentiment_score
                        ) / 2
                    else:
                        current_stats.average_sentiment_score = average_sentiment_score

                if dominant_emotion:
                    current_stats.dominant_emotion = dominant_emotion

                if emotion_distribution:
                    # Merge emotion distributions
                    existing = current_stats.emotion_distribution or {}
                    for emotion, value in emotion_distribution.items():
                        if emotion in existing:
                            existing[emotion] = (existing[emotion] + value) / 2
                        else:
                            existing[emotion] = value
                    current_stats.emotion_distribution = existing

                current_stats.updated_at = datetime.now()
                self.session.commit()

                logger.info(f"✅ Updated statistics for speaker {speaker_id}")
                return current_stats
            else:
                # Create new stats
                stats_data = {
                    "total_speaking_time": total_speaking_time,
                    "total_word_count": total_word_count,
                    "total_segment_count": total_segment_count,
                    "average_speaking_rate": average_speaking_rate,
                    "average_sentiment_score": average_sentiment_score,
                    "dominant_emotion": dominant_emotion,
                    "emotion_distribution": emotion_distribution,
                }

                new_stats = SpeakerStats(
                    speaker_id=speaker_id,
                    stats_data=stats_data,
                    total_speaking_time=total_speaking_time,
                    total_word_count=total_word_count,
                    total_segment_count=total_segment_count,
                    average_speaking_rate=average_speaking_rate,
                    average_sentiment_score=average_sentiment_score,
                    dominant_emotion=dominant_emotion,
                    emotion_distribution=emotion_distribution,
                    stats_period="all_time",
                    is_current=True,
                )

                self.session.add(new_stats)
                self.session.commit()

                logger.info(f"✅ Created statistics for speaker {speaker_id}")
                return new_stats

        except Exception as e:
            self.session.rollback()
            logger.error(f"❌ Failed to update speaker statistics: {e}")
            raise

    def get_speaker_statistics(
        self, speaker_id: int, stats_period: str = "all_time"
    ) -> Optional[SpeakerStats]:
        """
        Get speaker statistics for a specific period.

        Args:
            speaker_id: ID of the speaker
            stats_period: Period to get stats for (all_time, monthly, weekly)

        Returns:
            Speaker statistics or None if not found
        """
        try:
            stats = (
                self.session.query(SpeakerStats)
                .filter(
                    SpeakerStats.speaker_id == speaker_id,
                    SpeakerStats.stats_period == stats_period,
                    SpeakerStats.is_current == True,
                )
                .first()
            )

            return stats

        except Exception as e:
            logger.error(f"❌ Failed to get speaker statistics: {e}")
            return None

    def get_all_speaker_statistics(self) -> List[Dict[str, Any]]:
        """
        Get statistics for all speakers.

        Returns:
            List of speaker statistics dictionaries
        """
        try:
            speakers = self.speaker_repo.find_speakers(active_only=True)
            statistics = []

            for speaker in speakers:
                stats = self.get_speaker_statistics(speaker.id)
                if stats:
                    statistics.append(
                        {
                            "speaker_id": speaker.id,
                            "speaker_name": speaker.name,
                            "display_name": speaker.display_name,
                            "total_speaking_time": stats.total_speaking_time,
                            "total_word_count": stats.total_word_count,
                            "total_segment_count": stats.total_segment_count,
                            "average_speaking_rate": stats.average_speaking_rate,
                            "average_sentiment_score": stats.average_sentiment_score,
                            "dominant_emotion": stats.dominant_emotion,
                            "conversation_count": self._get_conversation_count(
                                speaker.id
                            ),
                        }
                    )

            return statistics

        except Exception as e:
            logger.error(f"❌ Failed to get all speaker statistics: {e}")
            return []

    def _get_conversation_count(self, speaker_id: int) -> int:
        """Get the number of conversations a speaker has participated in."""
        try:
            count = (
                self.session.query(Session)
                .filter(Session.speaker_id == speaker_id)
                .distinct(Session.conversation_id)
                .count()
            )
            return count
        except Exception:
            return 0

    def generate_speaker_report(self, speaker_id: int) -> Dict[str, Any]:
        """
        Generate a comprehensive report for a speaker.

        Args:
            speaker_id: ID of the speaker

        Returns:
            Dictionary containing comprehensive speaker report
        """
        try:
            speaker = self.speaker_repo.get_speaker_by_id(speaker_id)
            if not speaker:
                return {}

            stats = self.get_speaker_statistics(speaker_id)

            # Get all sessions for this speaker
            sessions = (
                self.session.query(Session)
                .filter(Session.speaker_id == speaker_id)
                .all()
            )

            # Get all conversations
            conversation_ids = [s.conversation_id for s in sessions]
            conversations = (
                self.session.query(Conversation)
                .filter(Conversation.id.in_(conversation_ids))
                .all()
                if conversation_ids
                else []
            )

            report = {
                "speaker": {
                    "id": speaker.id,
                    "name": speaker.name,
                    "display_name": speaker.display_name,
                    "email": speaker.email,
                    "organization": speaker.organization,
                    "role": speaker.role,
                    "canonical_id": speaker.canonical_id,
                    "confidence_score": speaker.confidence_score,
                    "is_verified": speaker.is_verified,
                    "created_at": (
                        speaker.created_at.isoformat() if speaker.created_at else None
                    ),
                    "updated_at": (
                        speaker.updated_at.isoformat() if speaker.updated_at else None
                    ),
                },
                "statistics": {
                    "total_speaking_time": stats.total_speaking_time if stats else None,
                    "total_word_count": stats.total_word_count if stats else None,
                    "total_segment_count": stats.total_segment_count if stats else None,
                    "average_speaking_rate": (
                        stats.average_speaking_rate if stats else None
                    ),
                    "average_sentiment_score": (
                        stats.average_sentiment_score if stats else None
                    ),
                    "dominant_emotion": stats.dominant_emotion if stats else None,
                    "emotion_distribution": stats.emotion_distribution if stats else {},
                },
                "participation": {
                    "conversation_count": len(conversations),
                    "session_count": len(sessions),
                    "conversations": [
                        {
                            "id": conv.id,
                            "title": conv.title,
                            "duration_seconds": conv.duration_seconds,
                            "created_at": (
                                conv.created_at.isoformat() if conv.created_at else None
                            ),
                        }
                        for conv in conversations
                    ],
                },
            }

            return report

        except Exception as e:
            logger.error(f"❌ Failed to generate speaker report: {e}")
            return {}

    def close(self):
        """Close the database session."""
        if self.session:
            self.session.close()
