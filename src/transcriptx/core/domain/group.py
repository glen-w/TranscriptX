"""
Domain Group model (pure domain object).

Key scheme is fixed: grp_v1_<sha256> computed from ordered transcript_file UUIDs.
Do not change the scheme to avoid silent mismatches later.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from transcriptx.core.domain.transcript_set import TranscriptSet


_KEY_PREFIX = "grp_v1_"


@dataclass(frozen=True)
class Group:
    """Immutable domain group model."""

    uuid: str
    key: str
    transcript_file_uuids: List[str]
    name: Optional[str] = None
    type: str = "merged_event"
    description: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @staticmethod
    def compute_key(transcript_file_uuids: List[str]) -> str:
        """
        Compute deterministic key from ordered transcript_file UUIDs.

        Input order is significant. This scheme must never change.
        """
        normalized = [uuid.strip().lower() for uuid in transcript_file_uuids]
        payload = "|".join(normalized)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"{_KEY_PREFIX}{digest}"

    def to_transcript_set(self, transcript_paths: List[str]) -> TranscriptSet:
        """
        Build an in-memory TranscriptSet for aggregation from resolved paths.
        """
        metadata = dict(self.metadata)
        metadata["group_uuid"] = self.uuid
        metadata["group_key"] = self.key
        return TranscriptSet.create(
            transcript_ids=list(transcript_paths),
            name=self.name,
            metadata=metadata,
            key=self.key,
        )
