"""
Resolve analysis targets into analysis scope + ordered transcript members.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Literal, Optional, Tuple, Union
from uuid import NAMESPACE_URL, uuid5

from transcriptx.core.domain.group import GroupMember
from transcriptx.core.services.group_service import GroupService
from transcriptx.core.utils.logger import get_logger

logger = get_logger()


@dataclass(frozen=True)
class TranscriptRef:
    path: str

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError("TranscriptRef must set path.")


@dataclass(frozen=True)
class GroupRef:
    path: str

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError("GroupRef must set path.")


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
    id: Optional[int] = None
    uuid: Optional[str] = None
    source: Literal["file"] = "file"


def _resolve_transcript_file(path: str) -> Path:
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(str(resolved))
    if resolved.suffix.lower() != ".json":
        raise ValueError(
            f"Transcript target must point to a transcript JSON file: {path}"
        )
    return resolved


def resolve_analysis_target(
    target: AnalysisTargetRef,
) -> Tuple[AnalysisScope, List[Union[GroupMember, FileTranscriptMember]]]:
    if isinstance(target, TranscriptRef):
        resolved_path = _resolve_transcript_file(target.path)
        path_uuid = str(uuid5(NAMESPACE_URL, str(resolved_path)))
        scope = AnalysisScope(
            scope_type="transcript",
            uuid=path_uuid,
            key=path_uuid,
            display_name=resolved_path.stem,
        )
        member = FileTranscriptMember(
            file_path=str(resolved_path),
            file_name=resolved_path.name,
            id=None,
            uuid=path_uuid,
            source="file",
        )
        return scope, [member]

    if isinstance(target, GroupRef):
        group = GroupService.resolve_group_identifier(target.path)
        members = GroupService.get_members(group.group_id)
        if not members:
            raise ValueError("Group has no members.")
        scope = AnalysisScope(
            scope_type="group",
            uuid=group.group_id,
            key=group.group_id,
            display_name=group.name or group.group_id,
        )
        return scope, members

    raise TypeError("Unsupported analysis target ref.")
