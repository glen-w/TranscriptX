"""Typed contracts for library duplicate detection and removal.

Display strings belong in the Settings Storage panel, not here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


CONFIRM_DELETE_DUPLICATES = "DELETE DUPLICATES"


class DuplicateKind(str, Enum):
    AUDIO_BYTES = "audio_bytes"
    TRANSCRIPT_BYTES = "transcript_bytes"
    TRANSCRIPT_CONTENT = "transcript_content"
    LINKED_UNIT = "linked_unit"


class MemberRole(str, Enum):
    AUDIO = "audio"
    TRANSCRIPT = "transcript"


@dataclass(frozen=True)
class FileFingerprint:
    """Identity used to refuse delete when the file changed after preview."""

    path: Path
    size: int
    mtime_ns: int
    sha256: str


@dataclass(frozen=True)
class DuplicateMember:
    role: MemberRole
    fingerprint: FileFingerprint
    title: str
    is_keeper: bool
    unique_transcript_at_risk: bool = False


@dataclass(frozen=True)
class DuplicateGroup:
    group_id: str
    kind: DuplicateKind
    keeper: DuplicateMember
    extras: tuple[DuplicateMember, ...]
    unique_transcript_at_risk: bool = False


@dataclass(frozen=True)
class DuplicatePreview:
    plan_id: str
    groups: tuple[DuplicateGroup, ...]
    extra_count: int
    size_estimate_bytes: int
    unique_transcript_warnings: int
    blocking_errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    can_execute: bool = False


@dataclass(frozen=True)
class DuplicateAuthorization:
    acknowledged: bool
    phrase: str
    plan_id: str


@dataclass(frozen=True)
class DuplicateResult:
    ok: bool
    plan_id: str
    audio_deleted: int = 0
    transcripts_deleted: int = 0
    companions_deleted: int = 0
    skipped: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    dangling_speaker_links: int = 0
    emptied_groups: tuple[str, ...] = ()
    deleted_transcript_paths: tuple[str, ...] = ()
    deleted_audio_paths: tuple[str, ...] = ()


def authorization_is_valid(
    auth: DuplicateAuthorization, *, expected_plan_id: str
) -> bool:
    return (
        bool(auth.acknowledged)
        and auth.phrase == CONFIRM_DELETE_DUPLICATES
        and auth.plan_id == expected_plan_id
    )
