"""
Repository classes for TranscriptX database operations.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_

from transcriptx.core.utils.logger import get_logger
from ..models import SpeakerProfile, BehavioralFingerprint

logger = get_logger()


from .base import BaseRepository


class ProfileRepository(BaseRepository):
    """
    Repository for speaker profile and behavioral fingerprint operations.

    This repository provides methods for:
    - Creating and updating speaker profiles
    - Managing behavioral fingerprints
    - Profile versioning and history
    - Behavioral pattern analysis
    """

    def create_speaker_profile(
        self,
        speaker_id: int,
        profile_data: Dict[str, Any],
        preferences: Optional[Dict[str, Any]] = None,
        settings: Optional[Dict[str, Any]] = None,
        vocabulary_patterns: Optional[Dict[str, Any]] = None,
        speech_patterns: Optional[Dict[str, Any]] = None,
        emotion_patterns: Optional[Dict[str, Any]] = None,
        session_history: Optional[List[Dict[str, Any]]] = None,
        analysis_history: Optional[List[Dict[str, Any]]] = None,
    ) -> SpeakerProfile:
        """
        Create a new speaker profile.

        Args:
            speaker_id: Speaker ID
            profile_data: Complete profile data
            preferences: User preferences
            settings: Analysis settings
            vocabulary_patterns: Vocabulary analysis patterns
            speech_patterns: Speech pattern analysis
            emotion_patterns: Emotion pattern analysis
            session_history: Session history data
            analysis_history: Analysis history data

        Returns:
            Created speaker profile instance
        """
        try:
            # Deactivate current profile if it exists
            current_profile = self.get_current_profile(speaker_id)
            if current_profile:
                current_profile.is_current = False
                self.session.commit()

            # Create new profile
            profile = SpeakerProfile(
                speaker_id=speaker_id,
                profile_data=profile_data,
                preferences=preferences or {},
                settings=settings or {},
                vocabulary_patterns=vocabulary_patterns or {},
                speech_patterns=speech_patterns or {},
                emotion_patterns=emotion_patterns or {},
                session_history=session_history or [],
                analysis_history=analysis_history or [],
                profile_version=(
                    (current_profile.profile_version + 1) if current_profile else 1
                ),
            )

            self.session.add(profile)
            self.session.commit()

            logger.info(
                f"✅ Created speaker profile version {profile.profile_version} for speaker {speaker_id}"
            )
            return profile

        except Exception as e:
            self.session.rollback()
            self._handle_error("create_speaker_profile", e)

    def get_current_profile(self, speaker_id: int) -> Optional[SpeakerProfile]:
        """Get the current profile for a speaker."""
        try:
            return (
                self.session.query(SpeakerProfile)
                .filter(
                    and_(
                        SpeakerProfile.speaker_id == speaker_id,
                        SpeakerProfile.is_current == True,
                    )
                )
                .first()
            )
        except Exception as e:
            self._handle_error("get_current_profile", e)

    def create_behavioral_fingerprint(
        self,
        speaker_id: int,
        fingerprint_data: Dict[str, Any],
        vocabulary_fingerprint: Optional[Dict[str, Any]] = None,
        speech_rhythm: Optional[Dict[str, Any]] = None,
        emotion_signature: Optional[Dict[str, Any]] = None,
        interaction_style: Optional[Dict[str, Any]] = None,
        statistical_signatures: Optional[Dict[str, Any]] = None,
        temporal_patterns: Optional[Dict[str, Any]] = None,
        confidence_score: Optional[float] = None,
    ) -> BehavioralFingerprint:
        """
        Create a new behavioral fingerprint.

        Args:
            speaker_id: Speaker ID
            fingerprint_data: Complete fingerprint data
            vocabulary_fingerprint: Vocabulary patterns
            speech_rhythm: Speech rhythm patterns
            emotion_signature: Emotion patterns
            interaction_style: Interaction patterns
            statistical_signatures: Statistical patterns
            temporal_patterns: Time-based patterns
            confidence_score: Confidence score

        Returns:
            Created behavioral fingerprint instance
        """
        try:
            # Deactivate current fingerprint if it exists
            current_fingerprint = self.get_current_fingerprint(speaker_id)
            if current_fingerprint:
                current_fingerprint.is_current = False
                self.session.commit()

            # Create new fingerprint
            fingerprint = BehavioralFingerprint(
                speaker_id=speaker_id,
                fingerprint_data=fingerprint_data,
                vocabulary_fingerprint=vocabulary_fingerprint or {},
                speech_rhythm=speech_rhythm or {},
                emotion_signature=emotion_signature or {},
                interaction_style=interaction_style or {},
                statistical_signatures=statistical_signatures or {},
                temporal_patterns=temporal_patterns or {},
                fingerprint_version=(
                    (current_fingerprint.fingerprint_version + 1)
                    if current_fingerprint
                    else 1
                ),
                confidence_score=confidence_score,
            )

            self.session.add(fingerprint)
            self.session.commit()

            logger.info(
                f"✅ Created behavioral fingerprint version {fingerprint.fingerprint_version} for speaker {speaker_id}"
            )
            return fingerprint

        except Exception as e:
            self.session.rollback()
            self._handle_error("create_behavioral_fingerprint", e)

    def get_current_fingerprint(
        self, speaker_id: int
    ) -> Optional[BehavioralFingerprint]:
        """Get the current behavioral fingerprint for a speaker."""
        try:
            return (
                self.session.query(BehavioralFingerprint)
                .filter(
                    and_(
                        BehavioralFingerprint.speaker_id == speaker_id,
                        BehavioralFingerprint.is_current == True,
                    )
                )
                .first()
            )
        except Exception as e:
            self._handle_error("get_current_fingerprint", e)

    def update_profile_with_session_data(
        self, speaker_id: int, session_data: Dict[str, Any]
    ) -> Optional[SpeakerProfile]:
        """
        Update speaker profile with new session data.

        Args:
            speaker_id: Speaker ID
            session_data: New session data to incorporate

        Returns:
            Updated profile instance
        """
        try:
            current_profile = self.get_current_profile(speaker_id)
            if not current_profile:
                logger.warning(f"⚠️ No current profile found for speaker {speaker_id}")
                return None

            # Update session history
            session_history = current_profile.session_history.copy()
            session_history.append(
                {"timestamp": datetime.utcnow().isoformat(), "data": session_data}
            )

            # Keep only last 50 sessions
            if len(session_history) > 50:
                session_history = session_history[-50:]

            current_profile.session_history = session_history
            current_profile.updated_at = datetime.utcnow()

            self.session.commit()

            logger.info(
                f"✅ Updated profile for speaker {speaker_id} with session data"
            )
            return current_profile

        except Exception as e:
            self.session.rollback()
            self._handle_error("update_profile_with_session_data", e)
