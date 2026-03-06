"""
Repository classes for TranscriptX database operations.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, or_
from sqlalchemy.orm import joinedload

from transcriptx.core.utils.logger import get_logger
from ..models import Conversation, Session as DBSession, ConversationMetadata

logger = get_logger()


from .base import BaseRepository


class ConversationRepository(BaseRepository):
    """
    Repository for conversation-related database operations.

    This repository provides methods for:
    - Creating and managing conversations
    - Finding conversations by various criteria
    - Managing conversation metadata
    - Session management within conversations
    """

    def create_conversation(
        self,
        title: str,
        description: Optional[str] = None,
        meeting_id: Optional[str] = None,
        audio_file_path: Optional[str] = None,
        transcript_file_path: Optional[str] = None,
        readable_transcript_path: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        word_count: Optional[int] = None,
        speaker_count: Optional[int] = None,
        conversation_date: Optional[datetime] = None,
        analysis_config: Optional[Dict[str, Any]] = None,
    ) -> Conversation:
        """
        Create a new conversation.

        Args:
            title: Conversation title
            description: Conversation description
            meeting_id: Meeting identifier
            audio_file_path: Path to audio file
            transcript_file_path: Path to transcript file
            readable_transcript_path: Path to readable transcript
            duration_seconds: Duration in seconds
            word_count: Total word count
            speaker_count: Number of speakers
            conversation_date: Date of conversation
            analysis_config: Analysis configuration

        Returns:
            Created conversation instance
        """
        try:
            conversation = Conversation(
                title=title,
                description=description,
                meeting_id=meeting_id,
                audio_file_path=audio_file_path,
                transcript_file_path=transcript_file_path,
                readable_transcript_path=readable_transcript_path,
                duration_seconds=duration_seconds,
                word_count=word_count,
                speaker_count=speaker_count,
                conversation_date=conversation_date,
                analysis_config=analysis_config or {},
            )

            self.session.add(conversation)
            self.session.commit()

            logger.info(f"✅ Created conversation: {title}")
            return conversation

        except Exception as e:
            self.session.rollback()
            self._handle_error("create_conversation", e)

    def get_conversation_by_id(self, conversation_id: int) -> Optional[Conversation]:
        """Get conversation by ID."""
        try:
            return (
                self.session.query(Conversation)
                .filter(Conversation.id == conversation_id)
                .first()
            )
        except Exception as e:
            self._handle_error("get_conversation_by_id", e)

    def get_conversation_by_meeting_id(self, meeting_id: str) -> Optional[Conversation]:
        """Get conversation by meeting ID."""
        try:
            return (
                self.session.query(Conversation)
                .filter(Conversation.meeting_id == meeting_id)
                .first()
            )
        except Exception as e:
            self._handle_error("get_conversation_by_meeting_id", e)

    def find_conversation_by_transcript_path(
        self, transcript_path: str
    ) -> Optional[Conversation]:
        """
        Find conversation by transcript file path.

        Searches both transcript_file_path and readable_transcript_path fields.
        Also checks processing state for renamed files.

        Args:
            transcript_path: Path to transcript file (may be old path if file was renamed)

        Returns:
            Conversation instance if found, None otherwise
        """
        try:
            # First try direct lookup
            conversation = (
                self.session.query(Conversation)
                .filter(
                    or_(
                        Conversation.transcript_file_path == transcript_path,
                        Conversation.readable_transcript_path == transcript_path,
                    )
                )
                .first()
            )

            if conversation:
                return conversation

            # If not found, try to get current path from processing state (for renamed files)
            try:
                from transcriptx.cli.processing_state import (
                    get_current_transcript_path_from_state,
                )

                current_path = get_current_transcript_path_from_state(transcript_path)
                if current_path and current_path != transcript_path:
                    # Try lookup with current path
                    conversation = (
                        self.session.query(Conversation)
                        .filter(
                            or_(
                                Conversation.transcript_file_path == current_path,
                                Conversation.readable_transcript_path == current_path,
                            )
                        )
                        .first()
                    )
                    if conversation:
                        return conversation
            except (ImportError, Exception):
                # If processing state lookup fails, just return None
                pass

            return None
        except Exception as e:
            self._handle_error("find_conversation_by_transcript_path", e)

    def find_conversations(
        self,
        title_pattern: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[Conversation]:
        """
        Find conversations by various criteria.

        Args:
            title_pattern: Pattern to match in titles
            status: Analysis status filter
            date_from: Start date filter
            date_to: End date filter
            limit: Maximum number of results

        Returns:
            List of matching conversations
        """
        try:
            query = self.session.query(Conversation)

            if title_pattern:
                query = query.filter(Conversation.title.ilike(f"%{title_pattern}%"))

            if status:
                query = query.filter(Conversation.analysis_status == status)

            if date_from:
                query = query.filter(Conversation.conversation_date >= date_from)

            if date_to:
                query = query.filter(Conversation.conversation_date <= date_to)

            query = query.order_by(desc(Conversation.created_at))

            if limit:
                query = query.limit(limit)

            return query.all()

        except Exception as e:
            self._handle_error("find_conversations", e)

    def update_conversation(
        self, conversation_id: int, **kwargs
    ) -> Optional[Conversation]:
        """
        Update conversation information.

        Args:
            conversation_id: Conversation ID to update
            **kwargs: Fields to update

        Returns:
            Updated conversation instance or None if not found
        """
        try:
            conversation = self.get_conversation_by_id(conversation_id)
            if not conversation:
                return None

            for key, value in kwargs.items():
                if hasattr(conversation, key):
                    setattr(conversation, key, value)

            conversation.updated_at = datetime.utcnow()
            self.session.commit()

            logger.info(f"✅ Updated conversation: {conversation.title}")
            return conversation

        except Exception as e:
            self.session.rollback()
            self._handle_error("update_conversation", e)

    def get_conversation_sessions(self, conversation_id: int) -> List[DBSession]:
        """Get all sessions for a conversation."""
        try:
            return (
                self.session.query(DBSession)
                .filter(DBSession.conversation_id == conversation_id)
                .options(joinedload(DBSession.speaker))
                .all()
            )
        except Exception as e:
            self._handle_error("get_conversation_sessions", e)

    def get_conversation_metadata(
        self, conversation_id: int
    ) -> List[ConversationMetadata]:
        """
        Get all metadata for a conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            List of ConversationMetadata instances
        """
        try:
            return (
                self.session.query(ConversationMetadata)
                .filter(ConversationMetadata.conversation_id == conversation_id)
                .all()
            )
        except Exception as e:
            self._handle_error("get_conversation_metadata", e)

    def add_conversation_metadata(
        self,
        conversation_id: int,
        key: str,
        value: str,
        value_type: str = "string",
        category: Optional[str] = None,
    ) -> ConversationMetadata:
        """
        Add metadata to a conversation.

        Args:
            conversation_id: Conversation ID
            key: Metadata key
            value: Metadata value
            value_type: Value type (string, number, boolean, json)
            category: Metadata category

        Returns:
            Created metadata instance
        """
        try:
            metadata = ConversationMetadata(
                conversation_id=conversation_id,
                key=key,
                value=value,
                value_type=value_type,
                category=category,
            )

            self.session.add(metadata)
            self.session.commit()

            logger.info(f"✅ Added metadata to conversation {conversation_id}: {key}")
            return metadata

        except Exception as e:
            self.session.rollback()
            self._handle_error("add_conversation_metadata", e)
