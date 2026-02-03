"""
Group service layer for TranscriptSet operations.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from transcriptx.core.domain.transcript_set import (  # type: ignore[import]
    TranscriptSet as DomainTranscriptSet,
)
from transcriptx.core.utils.group_resolver import resolve_group  # type: ignore[import]
from transcriptx.core.utils.logger import get_logger  # type: ignore[import]
from transcriptx.database import get_session  # type: ignore[import]
from transcriptx.database.models.transcript_set import TranscriptSet  # type: ignore[import]
from transcriptx.database.repositories.transcript_set import (  # type: ignore[import]
    TranscriptSetRepository,
)

logger = get_logger()


class GroupService:
    @staticmethod
    def list_groups() -> List[TranscriptSet]:
        session = get_session()
        try:
            repo = TranscriptSetRepository(session)
            return repo.list_sets()
        finally:
            session.close()

    @staticmethod
    def get_group(identifier: str) -> TranscriptSet:
        return resolve_group(identifier)

    @staticmethod
    def get_members(group: TranscriptSet) -> List[Any]:
        session = get_session()
        try:
            repo = TranscriptSetRepository(session)
            return repo.resolve_members(group)
        finally:
            session.close()

    @staticmethod
    def create_group(
        name: Optional[str],
        transcript_ids: List[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TranscriptSet:
        """
        Create a TranscriptSet using the same deterministic logic as CLI.
        """
        transcript_set = DomainTranscriptSet.create(
            transcript_ids=transcript_ids, name=name, metadata=metadata or {}
        )
        session = get_session()
        try:
            repo = TranscriptSetRepository(session)
            existing = repo.get_by_key(transcript_set.key)
            if existing:
                logger.info(
                    "TranscriptSet already exists, skipping creation for key %s",
                    transcript_set.key,
                )
                return existing
            return repo.create_transcript_set(
                name=transcript_set.name,
                transcript_ids=transcript_set.transcript_ids,
                metadata=transcript_set.metadata,
            )
        finally:
            session.close()

    @staticmethod
    def delete_group(identifier: str) -> None:
        group = resolve_group(identifier)
        group_uuid = group.uuid
        session = get_session()
        try:
            repo = TranscriptSetRepository(session)
            refreshed = repo.get_by_uuid(group_uuid)
            if refreshed is None:
                return
            repo.delete_transcript_set(refreshed)
        finally:
            session.close()
