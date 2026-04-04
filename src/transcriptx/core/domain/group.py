"""
Domain Group model (file-backed group manifest).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from transcriptx.core.domain.transcript_set import TranscriptSet


@dataclass(frozen=True)
class GroupMember:
    file_path: str
    file_name: str
    uuid: str
    id: Optional[int] = None
    source: str = "file"


@dataclass(frozen=True)
class Group:
    group_id: str
    name: str
    members: List[str]
    description: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    version: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def uuid(self) -> str:
        return self.group_id

    @property
    def key(self) -> str:
        return self.group_id

    @property
    def id(self) -> str:
        return self.group_id

    @property
    def type(self) -> str:
        return "group"

    @property
    def transcript_file_uuids(self) -> List[str]:
        return list(self.members)

    @staticmethod
    def compute_key(transcript_file_uuids: List[str]) -> str:
        normalized = [uuid.strip().lower() for uuid in transcript_file_uuids]
        payload = "|".join(normalized)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"grp_v1_{digest}"

    def to_manifest(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "group_id": self.group_id,
            "name": self.name,
            "description": self.description,
            "members": list(self.members),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def to_transcript_set(self, transcript_paths: List[str]) -> TranscriptSet:
        metadata = dict(self.metadata)
        metadata["group_uuid"] = self.group_id
        metadata["group_key"] = self.group_id
        return TranscriptSet.create(
            transcript_ids=list(transcript_paths),
            name=self.name,
            metadata=metadata,
            key=self.group_id,
        )
