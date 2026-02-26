"""
Resolve analysis targets into analysis scope + ordered transcript members.

Explicit refs prevent ambiguous string handling.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from typing import Iterable, List, Literal, Optional, Tuple, Union

from transcriptx.core.services.group_service import GroupService  # type: ignore[import]
from transcriptx.core.utils.logger import get_logger
from transcriptx.database import get_session  # type: ignore[import]
from transcriptx.database.models.transcript import TranscriptFile  # type: ignore[import]
from transcriptx.database.repositories.group import GroupRepository  # type: ignore[import]
from transcriptx.database.repositories.transcript import (  # type: ignore[import]
    TranscriptFileRepository,
)

logger = get_logger()


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


@dataclass(frozen=True)
class FileTranscriptMember:
    """File-only member for path-based analysis; no DB id or session."""

    file_path: str
    file_name: str
    id: Optional[int] = None  # no DB id in file-mode
    uuid: Optional[str] = None
    source: Literal["file"] = "file"


def resolve_analysis_target(
    target: AnalysisTargetRef,
) -> Tuple[AnalysisScope, List[Union[TranscriptFile, FileTranscriptMember]]]:
    """
    Resolve analysis target ref to scope and ordered transcript members.

    For TranscriptRef(path=...): file-mode only, never touches DB.
    For TranscriptRef(uuid=...) and GroupRef(...): DB-only; errors if DB unavailable.
    """
    # First branch: file path → file-mode only, no DB (invariant in code)
    if isinstance(target, TranscriptRef) and target.path:
        resolved_path = str(Path(target.path).expanduser().resolve())
        path_uuid = str(uuid5(NAMESPACE_URL, resolved_path))
        scope = AnalysisScope(
            scope_type="transcript",
            uuid=path_uuid,
            key=path_uuid,
            display_name=Path(resolved_path).stem,
        )
        member = FileTranscriptMember(
            file_path=resolved_path,
            file_name=Path(resolved_path).name,
            id=None,
            uuid=path_uuid,
            source="file",
        )
        logger.debug(
            "Resolved TranscriptRef(path=…) in file-mode (no DB). path=%s uuid=%s",
            resolved_path,
            path_uuid,
        )
        return scope, [member]

    # DB branches: TranscriptRef(uuid) and GroupRef
    if isinstance(target, TranscriptRef):
        session = get_session()
        try:
            repo = TranscriptFileRepository(session)
            uuid_val = target.transcript_file_uuid or target.transcript_uuid
            record = repo.get_transcript_file_by_uuid(uuid_val)
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


def resolve_group_member_ids(group_ref: GroupRef) -> List[int]:
    """
    Resolve ordered transcript_file IDs for a GroupRef.
    """
    identifier = (
        group_ref.group_uuid or group_ref.group_key or group_ref.group_name or ""
    )
    group = GroupService.resolve_group_identifier(identifier)
    if group.id is None:
        raise ValueError("Group identifier did not resolve to a persisted group.")
    session = get_session()
    try:
        repo = GroupRepository(session)
        members = repo.resolve_members(group.id)
        if not members:
            raise ValueError("Group has no members.")
        return [record.id for record in members]
    finally:
        session.close()


def resolve_transcript_paths(transcript_ids: Iterable[int]) -> List[Path]:
    """
    Resolve transcript file paths from ordered transcript_file IDs.
    """
    session = get_session()
    try:
        repo = TranscriptFileRepository(session)
        paths: List[Path] = []
        missing: List[int] = []
        for file_id in transcript_ids:
            record = repo.get_transcript_file_by_id(file_id)
            if record is None:
                missing.append(file_id)
                continue
            paths.append(Path(record.file_path))
        if missing:
            raise ValueError(f"Transcript files not found for IDs: {missing}")
        return paths
    finally:
        session.close()
