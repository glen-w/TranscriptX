"""
Database access utilities for TranscriptX web interface.

This module provides functions for accessing speaker database and profiles.
"""

from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
import json

from transcriptx.database.database import get_session
from transcriptx.database.models import Speaker, TranscriptFile, TranscriptSegment
from transcriptx.core.integration import DatabaseIntegrationPipeline
from transcriptx.core.utils.logger import get_logger
from transcriptx.web.services import FileService

from sqlalchemy import func

logger = get_logger()


def get_all_speakers() -> List[Dict[str, Any]]:
    """
    Get all speakers from database.

    Returns:
        List of speaker dictionaries
    """
    try:
        session = get_session()
        try:
            speakers = session.query(Speaker).all()
            result = []
            for speaker in speakers:
                result.append(
                    {
                        "id": speaker.id,
                        "name": speaker.name,
                        "display_name": speaker.display_name,
                        "first_name": speaker.first_name,
                        "surname": speaker.surname,
                        "personal_note": speaker.personal_note,
                        "email": speaker.email,
                        "organization": speaker.organization,
                        "role": speaker.role,
                        "color": speaker.color,
                        "avatar_url": speaker.avatar_url,
                        "is_verified": speaker.is_verified,
                        "is_active": speaker.is_active,
                        "created_at": (
                            speaker.created_at.isoformat()
                            if speaker.created_at
                            else None
                        ),
                        "updated_at": (
                            speaker.updated_at.isoformat()
                            if speaker.updated_at
                            else None
                        ),
                    }
                )
            return result
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Failed to get all speakers: {e}")
        return []


def get_speaker_by_id(speaker_id: int) -> Optional[Dict[str, Any]]:
    """
    Get speaker by ID.

    Args:
        speaker_id: Speaker ID

    Returns:
        Speaker dictionary or None if not found
    """
    try:
        session = get_session()
        try:
            speaker = session.query(Speaker).filter(Speaker.id == speaker_id).first()
            if not speaker:
                return None

            return {
                "id": speaker.id,
                "name": speaker.name,
                "display_name": speaker.display_name,
                "first_name": speaker.first_name,
                "surname": speaker.surname,
                "personal_note": speaker.personal_note,
                "email": speaker.email,
                "organization": speaker.organization,
                "role": speaker.role,
                "color": speaker.color,
                "avatar_url": speaker.avatar_url,
                "canonical_id": speaker.canonical_id,
                "confidence_score": speaker.confidence_score,
                "is_verified": speaker.is_verified,
                "is_active": speaker.is_active,
                "created_at": (
                    speaker.created_at.isoformat() if speaker.created_at else None
                ),
                "updated_at": (
                    speaker.updated_at.isoformat() if speaker.updated_at else None
                ),
            }
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Failed to get speaker by ID {speaker_id}: {e}")
        return None


def get_speaker_by_name(name: str) -> Optional[Dict[str, Any]]:
    """
    Get speaker by name.

    Args:
        name: Speaker name

    Returns:
        Speaker dictionary or None if not found
    """
    try:
        session = get_session()
        try:
            speaker = session.query(Speaker).filter(Speaker.name == name).first()
            if not speaker:
                return None

            return get_speaker_by_id(speaker.id)
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Failed to get speaker by name {name}: {e}")
        return None


def get_speaker_profiles(speaker_id: int) -> Dict[str, Any]:
    """
    Get all profile data for a speaker.

    Args:
        speaker_id: Speaker ID

    Returns:
        Dictionary containing all profile data
    """
    try:
        session = get_session()
        try:
            pipeline = DatabaseIntegrationPipeline(session)
            profile_data = pipeline.persistence_service.get_speaker_profile(speaker_id)
            return profile_data or {}
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Failed to get speaker profiles for {speaker_id}: {e}")
        return {}


def create_speaker(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Create new speaker.

    Args:
        data: Speaker data dictionary

    Returns:
        Created speaker dictionary or None if creation failed
    """
    try:
        session = get_session()
        try:
            # Validate required fields
            if "name" not in data or not data["name"]:
                raise ValueError("Speaker name is required")

            # Check if speaker already exists
            existing = (
                session.query(Speaker).filter(Speaker.name == data["name"]).first()
            )
            if existing:
                raise ValueError(f"Speaker with name '{data['name']}' already exists")

            # Create new speaker
            speaker = Speaker(
                name=data["name"],
                display_name=data.get("display_name"),
                email=data.get("email"),
                organization=data.get("organization"),
                role=data.get("role"),
                color=data.get("color"),
                avatar_url=data.get("avatar_url"),
                is_verified=data.get("is_verified", False),
                is_active=data.get("is_active", True),
            )

            session.add(speaker)
            session.commit()
            session.refresh(speaker)

            logger.info(f"Created speaker: {speaker.name} (ID: {speaker.id})")
            return get_speaker_by_id(speaker.id)
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create speaker: {e}")
            raise
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Failed to create speaker: {e}")
        return None


def update_speaker(speaker_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Update speaker information.

    Args:
        speaker_id: Speaker ID
        data: Updated speaker data dictionary

    Returns:
        Updated speaker dictionary or None if update failed
    """
    try:
        session = get_session()
        try:
            speaker = session.query(Speaker).filter(Speaker.id == speaker_id).first()
            if not speaker:
                raise ValueError(f"Speaker with ID {speaker_id} not found")

            # Update fields
            if "name" in data and data["name"]:
                # Check if name is already taken by another speaker
                existing = (
                    session.query(Speaker)
                    .filter(Speaker.name == data["name"], Speaker.id != speaker_id)
                    .first()
                )
                if existing:
                    raise ValueError(
                        f"Speaker with name '{data['name']}' already exists"
                    )
                speaker.name = data["name"]

            if "display_name" in data:
                speaker.display_name = data["display_name"]
            if "email" in data:
                speaker.email = data["email"]
            if "organization" in data:
                speaker.organization = data["organization"]
            if "role" in data:
                speaker.role = data["role"]
            if "color" in data:
                speaker.color = data["color"]
            if "avatar_url" in data:
                speaker.avatar_url = data["avatar_url"]
            if "is_verified" in data:
                speaker.is_verified = data["is_verified"]
            if "is_active" in data:
                speaker.is_active = data["is_active"]

            session.commit()
            session.refresh(speaker)

            logger.info(f"Updated speaker: {speaker.name} (ID: {speaker.id})")
            return get_speaker_by_id(speaker.id)
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update speaker {speaker_id}: {e}")
            raise
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Failed to update speaker {speaker_id}: {e}")
        return None


def delete_speaker(speaker_id: int) -> bool:
    """
    Delete/deactivate speaker.

    Args:
        speaker_id: Speaker ID

    Returns:
        True if successful, False otherwise
    """
    try:
        session = get_session()
        try:
            speaker = session.query(Speaker).filter(Speaker.id == speaker_id).first()
            if not speaker:
                raise ValueError(f"Speaker with ID {speaker_id} not found")

            # Soft delete by setting is_active to False
            speaker.is_active = False
            session.commit()

            logger.info(f"Deactivated speaker: {speaker.name} (ID: {speaker.id})")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to delete speaker {speaker_id}: {e}")
            raise
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Failed to delete speaker {speaker_id}: {e}")
        return False


def get_speaker_statistics(speaker_id: int) -> Dict[str, Any]:
    """
    Get speaker statistics and metadata.

    Args:
        speaker_id: Speaker ID

    Returns:
        Dictionary containing statistics
    """
    try:
        session = get_session()
        try:
            pipeline = DatabaseIntegrationPipeline(session)
            stats = pipeline.persistence_service.get_speaker_statistics(speaker_id)
            return stats or {}
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Failed to get speaker statistics for {speaker_id}: {e}")
        return {}


def get_speaker_conversations(speaker_id: int) -> List[Dict[str, Any]]:
    """
    Get all conversations a speaker has participated in.

    Args:
        speaker_id: Speaker ID

    Returns:
        List of conversation dictionaries
    """
    try:
        from transcriptx.database.models import Session as DBSession, Conversation

        session = get_session()
        try:
            speaker_sessions = (
                session.query(DBSession)
                .filter(DBSession.speaker_id == speaker_id)
                .all()
            )

            conversations = []
            seen_conversation_ids = set()

            for speaker_session in speaker_sessions:
                conv_id = speaker_session.conversation_id
                if conv_id in seen_conversation_ids:
                    continue
                seen_conversation_ids.add(conv_id)

                conversation = (
                    session.query(Conversation)
                    .filter(Conversation.id == conv_id)
                    .first()
                )

                if conversation:
                    conversations.append(
                        {
                            "id": conversation.id,
                            "title": conversation.title,
                            "created_at": (
                                conversation.created_at.isoformat()
                                if conversation.created_at
                                else None
                            ),
                            "speaking_time": speaker_session.speaking_time_seconds,
                            "word_count": speaker_session.word_count,
                            "segment_count": speaker_session.segment_count,
                        }
                    )

            return sorted(
                conversations, key=lambda x: x.get("created_at", ""), reverse=True
            )
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Failed to get conversations for speaker {speaker_id}: {e}")
        return []


def format_speaker_profile_data(profiles: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format speaker profile data for display.

    Args:
        profiles: Raw profile data dictionary

    Returns:
        Formatted profile data with extracted metrics
    """
    formatted = {
        "behavioral_patterns": {},
        "speaking_metrics": {},
        "sentiment_profile": {},
        "emotion_profile": {},
        "vocabulary_patterns": {},
    }

    if not profiles:
        return formatted

    # Extract behavioral patterns
    for profile_type, profile_data in profiles.items():
        if isinstance(profile_data, dict):
            if "speech_patterns" in profile_data:
                formatted["speaking_metrics"].update(
                    profile_data.get("speech_patterns", {})
                )
            if "sentiment_patterns" in profile_data:
                formatted["sentiment_profile"].update(
                    profile_data.get("sentiment_patterns", {})
                )
            if "emotion_patterns" in profile_data:
                formatted["emotion_profile"].update(
                    profile_data.get("emotion_patterns", {})
                )
            if "vocabulary_patterns" in profile_data:
                formatted["vocabulary_patterns"].update(
                    profile_data.get("vocabulary_patterns", {})
                )
            if "behavioral_patterns" in profile_data:
                formatted["behavioral_patterns"].update(
                    profile_data.get("behavioral_patterns", {})
                )

    return formatted


def get_transcript_file_for_run(
    session_slug: str, run_id: str
) -> Optional[TranscriptFile]:
    """
    Resolve TranscriptFile for a given UI run.

    Args:
        session_slug: Selected session slug from sidebar
        run_id: Selected run id from sidebar
    """
    run_dir = FileService._resolve_session_dir(f"{session_slug}/{run_id}")
    manifest_path = run_dir / ".transcriptx" / "manifest.json"
    transcript_path = None
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as handle:
                manifest = json.load(handle)
            transcript_path = manifest.get("transcript_path")
        except Exception as e:
            logger.warning(f"Failed to read manifest {manifest_path}: {e}")
    if not transcript_path:
        return None
    transcript_path = str(Path(transcript_path).resolve())

    session = get_session()
    try:
        return (
            session.query(TranscriptFile)
            .filter(TranscriptFile.file_path == transcript_path)
            .first()
        )
    except Exception as e:
        logger.error(f"Failed to resolve transcript file for {transcript_path}: {e}")
        return None
    finally:
        session.close()


def get_speaker_segments_for_transcript(
    speaker_id: int, transcript_file_id: int, limit: Optional[int] = None
) -> List[TranscriptSegment]:
    """Fetch speaker segments ordered by segment_index."""
    session = get_session()
    try:
        query = (
            session.query(TranscriptSegment)
            .filter(
                TranscriptSegment.transcript_file_id == transcript_file_id,
                TranscriptSegment.speaker_id == speaker_id,
            )
            .order_by(TranscriptSegment.segment_index.asc())
        )
        if limit:
            query = query.limit(limit)
        return query.all()
    except Exception as e:
        logger.error(
            f"Failed to get speaker segments for transcript {transcript_file_id}: {e}"
        )
        return []
    finally:
        session.close()


def get_other_segments_for_transcript(
    speaker_id: int,
    transcript_file_id: int,
    max_other_speakers: int,
    max_other_segments_total: int,
    max_other_segments_per_speaker: int,
) -> List[TranscriptSegment]:
    """
    Fetch a bounded sample of other-speaker segments for the same transcript.
    """
    session = get_session()
    try:
        other_ids = (
            session.query(TranscriptSegment.speaker_id)
            .filter(
                TranscriptSegment.transcript_file_id == transcript_file_id,
                TranscriptSegment.speaker_id.isnot(None),
                TranscriptSegment.speaker_id != speaker_id,
            )
            .distinct()
            .order_by(TranscriptSegment.speaker_id.asc())
            .limit(max_other_speakers)
            .all()
        )
        other_ids = [item[0] for item in other_ids if item[0] is not None]
        results: List[TranscriptSegment] = []
        for other_id in other_ids:
            remaining = max_other_segments_total - len(results)
            if remaining <= 0:
                break
            per_limit = min(max_other_segments_per_speaker, remaining)
            rows = (
                session.query(TranscriptSegment)
                .filter(
                    TranscriptSegment.transcript_file_id == transcript_file_id,
                    TranscriptSegment.speaker_id == other_id,
                )
                .order_by(TranscriptSegment.segment_index.asc())
                .limit(per_limit)
                .all()
            )
            results.extend(rows)
        return results
    except Exception as e:
        logger.error(
            f"Failed to get other segments for transcript {transcript_file_id}: {e}"
        )
        return []
    finally:
        session.close()


def get_transcript_revision_signal(
    transcript_file_id: int,
) -> Tuple[Optional[str], Optional[int], Optional[int]]:
    """
    Return (max_updated_at_iso, segment_count, max_segment_index).
    """
    session = get_session()
    try:
        max_updated = (
            session.query(func.max(TranscriptSegment.updated_at))
            .filter(TranscriptSegment.transcript_file_id == transcript_file_id)
            .scalar()
        )
        count = (
            session.query(func.count(TranscriptSegment.id))
            .filter(TranscriptSegment.transcript_file_id == transcript_file_id)
            .scalar()
        )
        max_index = (
            session.query(func.max(TranscriptSegment.segment_index))
            .filter(TranscriptSegment.transcript_file_id == transcript_file_id)
            .scalar()
        )
        max_updated_iso = max_updated.isoformat() if max_updated else None
        return max_updated_iso, int(count or 0), int(max_index or 0)
    except Exception as e:
        logger.error(
            f"Failed to get revision signal for transcript {transcript_file_id}: {e}"
        )
        return None, None, None
    finally:
        session.close()


def get_speakers_for_transcript(transcript_file_id: int) -> List[Dict[str, Any]]:
    """
    Get all speakers for a transcript file.

    Args:
        transcript_file_id: Transcript file ID

    Returns:
        List of speaker dictionaries
    """
    try:
        from transcriptx.database.models import TranscriptSegment

        session = get_session()
        try:
            # Get unique speaker IDs from segments
            speaker_ids = (
                session.query(TranscriptSegment.speaker_id)
                .filter(
                    TranscriptSegment.transcript_file_id == transcript_file_id,
                    TranscriptSegment.speaker_id.isnot(None),
                )
                .distinct()
                .all()
            )

            speakers = []
            for (speaker_id,) in speaker_ids:
                speaker = (
                    session.query(Speaker).filter(Speaker.id == speaker_id).first()
                )
                if speaker:
                    speakers.append(get_speaker_by_id(speaker.id))

            return speakers
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Failed to get speakers for transcript {transcript_file_id}: {e}")
        return []


def resolve_speaker_name(speaker_identifier: Any) -> Optional[str]:
    """
    Resolve a speaker identifier to a display name from the database.

    Args:
        speaker_identifier: Can be:
            - Database speaker ID (int)
            - Speaker name (str)
            - Speaker object with id or name

    Returns:
        Display name or None if not found
    """
    try:
        from transcriptx.core.utils.speaker import format_speaker_display_name

        session = get_session()
        try:
            speaker = None

            # Try by ID first
            if isinstance(speaker_identifier, int):
                speaker = (
                    session.query(Speaker)
                    .filter(Speaker.id == speaker_identifier)
                    .first()
                )
            # Try by name
            elif isinstance(speaker_identifier, str):
                speaker = (
                    session.query(Speaker)
                    .filter(Speaker.name == speaker_identifier)
                    .first()
                )
            # Try by object attribute
            elif hasattr(speaker_identifier, "id"):
                speaker = (
                    session.query(Speaker)
                    .filter(Speaker.id == speaker_identifier.id)
                    .first()
                )
            elif hasattr(speaker_identifier, "name"):
                speaker = (
                    session.query(Speaker)
                    .filter(Speaker.name == speaker_identifier.name)
                    .first()
                )

            if speaker:
                return format_speaker_display_name(
                    first_name=speaker.first_name,
                    surname=speaker.surname,
                    display_name=speaker.display_name,
                    name=speaker.name,
                )

            return None
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Failed to resolve speaker name for {speaker_identifier}: {e}")
        return None
