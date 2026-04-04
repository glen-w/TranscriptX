"""Group service layer."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from transcriptx.core.domain.group import Group, GroupMember
from transcriptx.core.store.group_manifest_store import GroupManifestStore
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import PATHS, PROJECT_ROOT

logger = get_logger()
_STORE = GroupManifestStore()


def _group_by_identifier(identifier: str) -> Group:
    return _STORE.resolve_group_identifier(identifier)


def _normalise_transcript_ref(ref: str) -> str:
    path = Path(ref).expanduser()
    if path.is_absolute():
        resolved = path.resolve()
    else:
        resolved = (Path(PROJECT_ROOT) / path).resolve()
    if not resolved.exists():
        raise ValueError(f"Transcript files not found: {ref}")
    project_root_resolved = Path(PROJECT_ROOT).resolve()
    transcripts_dir_resolved = Path(PATHS.transcripts_dir).resolve()
    try:
        rel = resolved.relative_to(project_root_resolved)
        return str(rel)
    except ValueError:
        pass
    try:
        rel = resolved.relative_to(transcripts_dir_resolved)
        return str(rel)
    except ValueError as exc:
        raise ValueError(f"Transcript paths must be project-relative: {ref}") from exc


class GroupService:
    @staticmethod
    def resolve_group_identifier(identifier: str) -> Group:
        return _group_by_identifier(identifier)

    @staticmethod
    def list_groups(group_type: Optional[str] = None) -> List[Group]:
        groups = _STORE.list_groups()
        if group_type is None:
            return groups
        return groups

    @staticmethod
    def get_members(group_id: str) -> List[GroupMember]:
        group = _group_by_identifier(group_id)
        return _STORE.resolve_group_members(group)

    @staticmethod
    def delete_group(identifier: str) -> bool:
        group = _group_by_identifier(identifier)
        return _STORE.delete(group.group_id)

    @staticmethod
    def rename_group(identifier: str, name: str) -> Group:
        name = name.strip()
        if not name:
            raise ValueError("Group name cannot be empty.")
        group = _group_by_identifier(identifier)
        if name == (group.name or "").strip():
            return group
        updated = _STORE.update_group(group, name=name)
        return updated

    @staticmethod
    def update_membership(identifier: str, transcript_refs: Sequence[str]) -> Group:
        group = _group_by_identifier(identifier)
        if not transcript_refs:
            raise ValueError("Group must have at least one transcript.")
        updated = _STORE.update_group(group, members=transcript_refs)
        return updated

    @staticmethod
    def create_or_get_group(
        name: Optional[str],
        group_type: str,
        transcript_refs: Sequence[str],
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Group:
        transcript_paths = [_normalise_transcript_ref(ref) for ref in transcript_refs]
        if not transcript_paths:
            raise ValueError("Group must contain at least one transcript path.")
        for existing in _STORE.list_groups_best_effort()[0]:
            if existing.members == transcript_paths:
                logger.info(
                    "Group already exists for these members; reusing %s",
                    existing.group_id,
                )
                return existing
        return _STORE.create_group(
            name=name or "Unnamed",
            members=transcript_paths,
            description=description,
        )

    @staticmethod
    def create_or_get_group_with_status(
        name: Optional[str],
        group_type: str,
        transcript_refs: Sequence[str],
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Group, bool]:
        transcript_paths = [_normalise_transcript_ref(ref) for ref in transcript_refs]
        if not transcript_paths:
            raise ValueError("Group must contain at least one transcript path.")
        for existing in _STORE.list_groups_best_effort()[0]:
            if existing.members == transcript_paths:
                logger.info(
                    "Group already exists for these members; reusing %s",
                    existing.group_id,
                )
                return existing, False
        created = _STORE.create_group(
            name=name or "Unnamed",
            members=transcript_paths,
            description=description,
        )
        return created, True

    @staticmethod
    def validate_transcripts_exist(transcript_refs: Sequence[str]) -> None:
        missing = []
        for ref in transcript_refs:
            try:
                _normalise_transcript_ref(ref)
            except Exception:
                missing.append(ref)
        if missing:
            raise ValueError(f"Transcript files not found: {missing}")
