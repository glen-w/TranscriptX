"""
Resolve TranscriptSet identifiers to persisted groups.
"""

from __future__ import annotations

import re
from typing import Optional

from transcriptx.core.domain.transcript_set import (  # type: ignore[import]
    TranscriptSet as DomainTranscriptSet,
)
from transcriptx.core.utils.logger import get_logger  # type: ignore[import]
from transcriptx.database import get_session  # type: ignore[import]
from transcriptx.database.models.transcript_set import TranscriptSet  # type: ignore[import]
from transcriptx.database.repositories.transcript_set import (  # type: ignore[import]
    TranscriptSetRepository,
)

logger = get_logger()


_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_KEY_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def _is_uuid(value: str) -> bool:
    return bool(_UUID_RE.match(value))


def _is_key(value: str) -> bool:
    return bool(_KEY_RE.match(value))


def resolve_group(identifier: str) -> TranscriptSet:
    """
    Resolve an identifier to a TranscriptSet model.

    Identifier can be UUID, deterministic key, or unique name.
    """
    session = get_session()
    try:
        repo = TranscriptSetRepository(session)
        if _is_uuid(identifier):
            found = repo.get_by_uuid(identifier)
            if found:
                return found
        if _is_key(identifier):
            found = repo.get_by_key(identifier)
            if found:
                return found

        matches = (
            session.query(TranscriptSet).filter(TranscriptSet.name == identifier).all()
        )
        if not matches:
            raise ValueError(f"No TranscriptSet found for identifier: {identifier}")
        if len(matches) > 1:
            raise ValueError(
                "Multiple TranscriptSets share this name; use UUID or key instead."
            )
        return matches[0]
    finally:
        session.close()


def to_domain_transcript_set(model: TranscriptSet) -> DomainTranscriptSet:
    """
    Convert persisted TranscriptSet model to domain TranscriptSet.
    """
    return DomainTranscriptSet.create(
        transcript_ids=list(model.transcript_ids or []),
        name=model.name,
        metadata=dict(model.set_metadata or {}),
    )
