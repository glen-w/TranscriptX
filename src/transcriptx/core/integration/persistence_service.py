"""
Persistence service for TranscriptX.

This module provides the PersistenceService class that handles storing
speaker data in the database and managing data persistence operations.
"""

import logging
from datetime import datetime
from typing import Any, Dict

from transcriptx.database.models import (
    SpeakerSentimentProfile,
    SpeakerEmotionProfile,
    SpeakerTopicProfile,
    SpeakerEntityProfile,
    SpeakerTicProfile,
    SpeakerSemanticProfile,
    SpeakerInteractionProfile,
    SpeakerPerformanceProfile,
)

logger = logging.getLogger(__name__)


class PersistenceService:
    """
    Persistence service for storing speaker data in the database.

    This service handles all database operations for storing speaker profile
    data and managing data persistence across different analysis types.
    """

    def __init__(self, database_session=None):
        """
        Initialize the persistence service.

        Args:
            database_session: SQLAlchemy database session
        """
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.session = database_session

        # Profile models mapping
        self.profile_models = {
            "sentiment": SpeakerSentimentProfile,
            "emotion": SpeakerEmotionProfile,
            "topic": SpeakerTopicProfile,
            "entity": SpeakerEntityProfile,
            "tic": SpeakerTicProfile,
            "semantic": SpeakerSemanticProfile,
            "interaction": SpeakerInteractionProfile,
            "performance": SpeakerPerformanceProfile,
        }

    def store_speaker_data(
        self, analysis_type: str, speaker_id: int, data: Dict[str, Any]
    ) -> bool:
        """
        Store speaker data for a specific analysis type.

        Args:
            analysis_type: Type of analysis (sentiment, emotion, etc.)
            speaker_id: ID of the speaker
            data: Data to store

        Returns:
            True if storage was successful

        Raises:
            ValueError: If analysis type is invalid
            Exception: If storage fails
        """
        if analysis_type not in self.profile_models:
            raise ValueError(f"Invalid analysis type: {analysis_type}")

        if not self.session:
            self.logger.warning("No database session available")
            return False

        try:
            model_class = self.profile_models[analysis_type]

            # Check if profile already exists
            existing_profile = (
                self.session.query(model_class)
                .filter(model_class.speaker_id == speaker_id)
                .first()
            )

            if existing_profile:
                # Update existing profile
                self._update_profile(existing_profile, data)
                self.logger.info(
                    f"Updated {analysis_type} profile for speaker {speaker_id}"
                )
            else:
                # Create new profile
                self._create_profile(model_class, speaker_id, data)
                self.logger.info(
                    f"Created {analysis_type} profile for speaker {speaker_id}"
                )

            # Commit changes
            self.session.commit()
            return True

        except Exception as e:
            self.logger.error(
                f"Error storing {analysis_type} data for speaker {speaker_id}: {str(e)}"
            )
            self.session.rollback()
            raise

    def _create_profile(
        self, model_class, speaker_id: int, data: Dict[str, Any]
    ) -> None:
        """
        Create a new profile in the database.

        Args:
            model_class: Profile model class
            speaker_id: ID of the speaker
            data: Profile data
        """
        profile_data = {
            "speaker_id": speaker_id,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        # Add analysis-specific fields
        for field, value in data.items():
            if hasattr(model_class, field):
                profile_data[field] = value

        new_profile = model_class(**profile_data)
        self.session.add(new_profile)

    def _update_profile(self, profile, data: Dict[str, Any]) -> None:
        """
        Update an existing profile in the database.

        Args:
            profile: Existing profile object
            data: New profile data
        """
        # Update analysis-specific fields
        for field, value in data.items():
            if hasattr(profile, field):
                setattr(profile, field, value)

        # Update timestamp
        profile.updated_at = datetime.now()

    def get_speaker_profile(
        self, speaker_id: int, analysis_type: str = None
    ) -> Dict[str, Any]:
        """
        Get speaker profile data from the database.

        Args:
            speaker_id: ID of the speaker
            analysis_type: Specific analysis type to retrieve (optional)

        Returns:
            Dictionary containing profile data
        """
        if not self.session:
            return {}

        try:
            if analysis_type:
                # Get specific profile type
                if analysis_type not in self.profile_models:
                    raise ValueError(f"Invalid analysis type: {analysis_type}")

                model_class = self.profile_models[analysis_type]
                profile = (
                    self.session.query(model_class)
                    .filter(model_class.speaker_id == speaker_id)
                    .first()
                )

                if profile:
                    return self._serialize_profile(profile)
                return {}

            else:
                # Get all profile types
                all_profiles = {}
                for analysis_type, model_class in self.profile_models.items():
                    profile = (
                        self.session.query(model_class)
                        .filter(model_class.speaker_id == speaker_id)
                        .first()
                    )

                    if profile:
                        all_profiles[analysis_type] = self._serialize_profile(profile)

                return all_profiles

        except Exception as e:
            self.logger.error(
                f"Error getting profile for speaker {speaker_id}: {str(e)}"
            )
            return {}

    def _serialize_profile(self, profile) -> Dict[str, Any]:
        """
        Serialize profile object to dictionary.

        Args:
            profile: Profile object

        Returns:
            Serialized profile data
        """
        profile_data = {}

        for column in profile.__table__.columns:
            value = getattr(profile, column.name)
            profile_data[column.name] = value

        return profile_data

    def clear_speaker_data(self, conversation_id: int, speaker_id: int) -> bool:
        """
        Clear all data for a specific speaker in a conversation.

        Args:
            conversation_id: ID of the conversation
            speaker_id: ID of the speaker

        Returns:
            True if clearing was successful
        """
        if not self.session:
            return False

        try:
            # Delete all profile types for the speaker
            for model_class in self.profile_models.values():
                self.session.query(model_class).filter(
                    model_class.speaker_id == speaker_id
                ).delete()

            self.session.commit()
            self.logger.info(f"Cleared all data for speaker {speaker_id}")
            return True

        except Exception as e:
            self.logger.error(f"Error clearing data for speaker {speaker_id}: {str(e)}")
            self.session.rollback()
            return False

    def get_processing_status(self, conversation_id: int) -> Dict[str, Any]:
        """
        Get processing status for a conversation.

        Args:
            conversation_id: ID of the conversation

        Returns:
            Dictionary containing processing status
        """
        if not self.session:
            return {}

        try:
            status = {
                "conversation_id": conversation_id,
                "total_speakers": 0,
                "processed_speakers": 0,
                "profile_counts": {},
                "last_updated": None,
            }

            # Count profiles by type
            for analysis_type, model_class in self.profile_models.items():
                count = self.session.query(model_class).count()
                status["profile_counts"][analysis_type] = count

            # Get last updated timestamp
            latest_timestamps = []
            for model_class in self.profile_models.values():
                latest = (
                    self.session.query(model_class.updated_at)
                    .order_by(model_class.updated_at.desc())
                    .first()
                )
                if latest and latest[0]:
                    latest_timestamps.append(latest[0])

            if latest_timestamps:
                status["last_updated"] = max(latest_timestamps)

            return status

        except Exception as e:
            self.logger.error(f"Error getting processing status: {str(e)}")
            return {}

    def get_speaker_statistics(self, speaker_id: int) -> Dict[str, Any]:
        """
        Get statistics for a specific speaker.

        Args:
            speaker_id: ID of the speaker

        Returns:
            Dictionary containing speaker statistics
        """
        if not self.session:
            return {}

        try:
            stats = {
                "speaker_id": speaker_id,
                "profile_count": 0,
                "analysis_types": [],
                "last_updated": None,
                "data_completeness": 0.0,
            }

            # Count profiles and get analysis types
            profile_count = 0
            latest_timestamps = []

            for analysis_type, model_class in self.profile_models.items():
                profile = (
                    self.session.query(model_class)
                    .filter(model_class.speaker_id == speaker_id)
                    .first()
                )

                if profile:
                    profile_count += 1
                    stats["analysis_types"].append(analysis_type)

                    if profile.updated_at:
                        latest_timestamps.append(profile.updated_at)

            stats["profile_count"] = profile_count
            stats["data_completeness"] = profile_count / len(self.profile_models)

            if latest_timestamps:
                stats["last_updated"] = max(latest_timestamps)

            return stats

        except Exception as e:
            self.logger.error(
                f"Error getting statistics for speaker {speaker_id}: {str(e)}"
            )
            return {}

    def export_speaker_data(self, speaker_id: int, format: str = "json") -> Any:
        """
        Export speaker data in specified format.

        Args:
            speaker_id: ID of the speaker
            format: Export format (json, csv, etc.)

        Returns:
            Exported data in specified format
        """
        if format.lower() != "json":
            raise ValueError(f"Unsupported export format: {format}")

        # Get all profile data
        all_profiles = self.get_speaker_profile(speaker_id)

        # Add metadata
        export_data = {
            "speaker_id": speaker_id,
            "export_timestamp": datetime.now().isoformat(),
            "profiles": all_profiles,
            "statistics": self.get_speaker_statistics(speaker_id),
        }

        return export_data
