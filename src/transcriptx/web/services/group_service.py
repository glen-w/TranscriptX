"""
Group service layer for web UI.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from transcriptx.core.domain.group import Group
from transcriptx.core.services.group_service import GroupService as CoreGroupService
from transcriptx.database.models.transcript import TranscriptFile


class GroupService:
    @staticmethod
    def list_groups(group_type: Optional[str] = None) -> List[Group]:
        return CoreGroupService.list_groups(group_type=group_type)

    @staticmethod
    def get_group(identifier: str) -> Group:
        return CoreGroupService.resolve_group_identifier(identifier)

    @staticmethod
    def get_members(group: Group) -> List[TranscriptFile]:
        if group.id is None:
            return []
        return CoreGroupService.get_members(group.id)

    @staticmethod
    def create_group(
        name: Optional[str],
        group_type: str,
        transcript_refs: List[str],
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Group:
        return CoreGroupService.create_or_get_group(
            name=name,
            group_type=group_type,
            transcript_refs=transcript_refs,
            description=description,
            metadata=metadata,
        )

    @staticmethod
    def delete_group(identifier: str) -> bool:
        return CoreGroupService.delete_group(identifier)
