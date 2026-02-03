"""
Resolve analysis targets into analysis scope + ordered transcript members.

Explicit refs prevent ambiguous string handling.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from typing import List, Optional, Tuple, Union

from transcriptx.core.services.group_service import GroupService  # type: ignore[import]
from transcriptx.database import get_session  # type: ignore[import]
from transcriptx.database.models.transcript import TranscriptFile  # type: ignore[import]
from transcriptx.database.repositories.group import GroupRepository  # type: ignore[import]
from transcriptx.database.repositories.transcript import (  # type: ignore[import]
    TranscriptFileRepository,
)


@dataclass(frozen=True)
class TranscriptRef:
    transcript_uuid: Optional[str] = None
    transcript_file_uuid: Optional[str] = None
    path: Optional[str] = None

    def __post_init__(self) -> None:
        set_count = sum(
            1
            for value in (self.transcript_uuid, self.transcript_file_uuid, self.path)
            if value
        )
        if set_count != 1:
            raise ValueError("TranscriptRef must set exactly one of uuid or path.")


@dataclass(frozen=True)
class GroupRef:
    group_uuid: Optional[str] = None
    group_key: Optional[str] = None
    group_name: Optional[str] = None

    def __post_init__(self) -> None:
        set_count = sum(
            1 for value in (self.group_uuid, self.group_key, self.group_name) if value
        )
        if set_count != 1:
            raise ValueError("GroupRef must set exactly one of uuid, key, or name.")


AnalysisTargetRef = Union[TranscriptRef, GroupRef]


@dataclass(frozen=True)
class AnalysisScope:
    scope_type: str  # "transcript" | "group"
    uuid: str
    key: str
    display_name: str


def resolve_analysis_target(
    target: AnalysisTargetRef,
) -> Tuple[AnalysisScope, List[TranscriptFile]]:
    """
    Resolve analysis target ref to scope and ordered transcript members.
    """
    if isinstance(target, TranscriptRef):
        session = get_session()
        try:
            repo = TranscriptFileRepository(session)
            record: Optional[TranscriptFile] = None
            if target.path:
                record = repo.get_transcript_file_by_path(target.path)
                if record is None:
                    path = str(target.path)
                    record = TranscriptFile(
                        file_path=path,
                        file_name=Path(path).name,
                        uuid=str(uuid5(NAMESPACE_URL, path)),
                    )
            else:
                uuid = target.transcript_file_uuid or target.transcript_uuid
                record = repo.get_transcript_file_by_uuid(uuid)
            if record is None:
                raise ValueError("Transcript file not found for provided reference.")
            scope = AnalysisScope(
                scope_type="transcript",
                uuid=record.uuid,
                key=record.uuid,
                display_name=record.file_name or record.file_path,
            )
            return scope, [record]
        finally:
            session.close()

    if isinstance(target, GroupRef):
        identifier = target.group_uuid or target.group_key or target.group_name or ""
        group = GroupService.resolve_group_identifier(identifier)
        if group.id is None:
            raise ValueError("Group identifier did not resolve to a persisted group.")
        session = get_session()
        try:
            repo = GroupRepository(session)
            members = repo.resolve_members(group.id)
            if not members:
                raise ValueError("Group has no members.")
            scope = AnalysisScope(
                scope_type="group",
                uuid=group.uuid,
                key=group.key,
                display_name=group.name or group.key,
            )
            return scope, members
        finally:
            session.close()

    raise TypeError("Unsupported analysis target ref.")
