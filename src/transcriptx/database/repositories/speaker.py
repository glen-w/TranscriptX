"""
Repository classes for TranscriptX database operations.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import and_, desc, func

from transcriptx.core.utils.logger import get_logger
from ..models import Speaker, SpeakerProfile, SpeakerStats

logger = get_logger()


from .base import BaseRepository


class SpeakerRepository(BaseRepository):
    """
    Repository for speaker-related database operations.

    This repository provides methods for:
    - Creating and updating speakers
    - Finding speakers by various criteria
    - Managing speaker profiles and fingerprints
    - Speaker statistics and analytics
    """

    def create_speaker(
        self,
        name: str,
        display_name: Optional[str] = None,
        first_name: Optional[str] = None,
        surname: Optional[str] = None,
        personal_note: Optional[str] = None,
        email: Optional[str] = None,
        organization: Optional[str] = None,
        role: Optional[str] = None,
        color: Optional[str] = None,
        avatar_url: Optional[str] = None,
    ) -> Speaker:
        """
        Create a new speaker.

        Args:
            name: Speaker's name (display name)
            display_name: Display name (optional)
            first_name: First name (optional)
            surname: Surname (optional)
            personal_note: Personal note for disambiguation (optional)
            email: Email address (optional)
            organization: Organization (optional)
            role: Role or title (optional)
            color: Hex color code (optional)
            avatar_url: Avatar URL (optional)

        Returns:
            Created speaker instance
        """
        try:
            speaker = Speaker(
                name=name,
                display_name=display_name,
                first_name=first_name,
                surname=surname,
                personal_note=personal_note,
                email=email,
                organization=organization,
                role=role,
                color=color,
                avatar_url=avatar_url,
            )

            self.session.add(speaker)
            self.session.commit()

            logger.info(f"✅ Created speaker: {name}")
            return speaker

        except Exception as e:
            self.session.rollback()
            self._handle_error("create_speaker", e)

    def get_speaker_by_id(self, speaker_id: int) -> Optional[Speaker]:
        """Get speaker by ID."""
        try:
            return self.session.query(Speaker).filter(Speaker.id == speaker_id).first()
        except Exception as e:
            self._handle_error("get_speaker_by_id", e)

    def get_speaker_by_name(self, name: str) -> Optional[Speaker]:
        """Get speaker by name."""
        try:
            return self.session.query(Speaker).filter(Speaker.name == name).first()
        except Exception as e:
            self._handle_error("get_speaker_by_name", e)

    def get_speaker_by_email(self, email: str) -> Optional[Speaker]:
        """Get speaker by email."""
        try:
            return self.session.query(Speaker).filter(Speaker.email == email).first()
        except Exception as e:
            self._handle_error("get_speaker_by_email", e)

    def get_speaker_by_canonical_id(self, canonical_id: str) -> Optional[Speaker]:
        """Get speaker by canonical_id."""
        try:
            return (
                self.session.query(Speaker)
                .filter(Speaker.canonical_id == canonical_id)
                .first()
            )
        except Exception as e:
            self._handle_error("get_speaker_by_canonical_id", e)

    def find_speakers(
        self,
        name_pattern: Optional[str] = None,
        organization: Optional[str] = None,
        active_only: bool = True,
    ) -> List[Speaker]:
        """
        Find speakers by various criteria.

        Args:
            name_pattern: Pattern to match in speaker names
            organization: Organization filter
            active_only: Only return active speakers

        Returns:
            List of matching speakers
        """
        try:
            query = self.session.query(Speaker)

            if active_only:
                query = query.filter(Speaker.is_active == True)

            if name_pattern:
                query = query.filter(Speaker.name.ilike(f"%{name_pattern}%"))

            if organization:
                query = query.filter(Speaker.organization == organization)

            return query.order_by(Speaker.name).all()

        except Exception as e:
            self._handle_error("find_speakers", e)

    def find_speakers_by_name(
        self, first_name: str, surname: Optional[str] = None, active_only: bool = True
    ) -> List[Speaker]:
        """
        Find speakers by first name and surname (for duplicate detection).

        Args:
            first_name: First name to match
            surname: Surname to match (optional)
            active_only: Only return active speakers

        Returns:
            List of matching speakers
        """
        try:
            query = self.session.query(Speaker)

            if active_only:
                query = query.filter(Speaker.is_active == True)

            # Match first_name (case-insensitive)
            query = query.filter(
                func.lower(Speaker.first_name) == func.lower(first_name)
            )

            # Match surname if provided
            if surname:
                query = query.filter(func.lower(Speaker.surname) == func.lower(surname))
            else:
                # If no surname provided, match speakers with no surname
                query = query.filter(Speaker.surname.is_(None))

            return query.order_by(Speaker.name).all()

        except Exception as e:
            self._handle_error("find_speakers_by_name", e)

    def update_speaker(self, speaker_id: int, **kwargs) -> Optional[Speaker]:
        """
        Update speaker information.

        Args:
            speaker_id: Speaker ID to update
            **kwargs: Fields to update

        Returns:
            Updated speaker instance or None if not found
        """
        try:
            speaker = self.get_speaker_by_id(speaker_id)
            if not speaker:
                return None

            for key, value in kwargs.items():
                if hasattr(speaker, key):
                    setattr(speaker, key, value)

            speaker.updated_at = datetime.utcnow()
            self.session.commit()

            logger.info(f"✅ Updated speaker: {speaker.name}")
            return speaker

        except Exception as e:
            self.session.rollback()
            self._handle_error("update_speaker", e)

    def deactivate_speaker(self, speaker_id: int) -> bool:
        """Deactivate a speaker."""
        try:
            speaker = self.get_speaker_by_id(speaker_id)
            if not speaker:
                return False

            speaker.is_active = False
            speaker.updated_at = datetime.utcnow()
            self.session.commit()

            logger.info(f"✅ Deactivated speaker: {speaker.name}")
            return True

        except Exception as e:
            self.session.rollback()
            self._handle_error("deactivate_speaker", e)

    def get_speaker_stats(self, speaker_id: int) -> Optional[SpeakerStats]:
        """Get current speaker statistics."""
        try:
            return (
                self.session.query(SpeakerStats)
                .filter(
                    and_(
                        SpeakerStats.speaker_id == speaker_id,
                        SpeakerStats.is_current == True,
                    )
                )
                .first()
            )
        except Exception as e:
            self._handle_error("get_speaker_stats", e)

    def get_speaker_profiles(self, speaker_id: int) -> List[SpeakerProfile]:
        """Get all profiles for a speaker."""
        try:
            return (
                self.session.query(SpeakerProfile)
                .filter(SpeakerProfile.speaker_id == speaker_id)
                .order_by(desc(SpeakerProfile.profile_version))
                .all()
            )
        except Exception as e:
            self._handle_error("get_speaker_profiles", e)

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
