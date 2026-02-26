"""Group service layer."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

from transcriptx.core.domain.group import Group
from transcriptx.core.utils.logger import get_logger
from transcriptx.database import get_session
from transcriptx.database.models.transcript import TranscriptFile
from transcriptx.database.repositories.group import GroupRepository
from transcriptx.database.repositories.transcript import TranscriptFileRepository

logger = get_logger()

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-" r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_KEY_RE = re.compile(r"^grp_v1_[0-9a-f]{64}$")


def _looks_like_uuid(value: str) -> bool:
    return bool(_UUID_RE.match(value))


def _looks_like_key(value: str) -> bool:
    return bool(_KEY_RE.match(value))


class GroupService:
    @staticmethod
    def resolve_group_identifier(identifier: str) -> Group:
        """
        Resolve group identifier (uuid, key, or unique name).
        """
        session = get_session()
        try:
            repo = GroupRepository(session)
            if _looks_like_uuid(identifier):
                found = repo.get_by_uuid(identifier)
                if found:
                    return found
            if _looks_like_key(identifier):
                found = repo.get_by_key(identifier)
                if found:
                    return found

            matches = repo.list_by_name(identifier)
            if not matches:
                raise ValueError(f"No group found for identifier: {identifier}")
            if len(matches) > 1:
                raise ValueError(
                    "Multiple groups share this name; use uuid or key instead."
                )
            return matches[0]
        finally:
            session.close()

    @staticmethod
    def list_groups(group_type: Optional[str] = None) -> List[Group]:
        session = get_session()
        try:
            repo = GroupRepository(session)
            return repo.list_groups(group_type=group_type)
        finally:
            session.close()

    @staticmethod
    def get_members(group_id: int) -> List[TranscriptFile]:
        session = get_session()
        try:
            repo = GroupRepository(session)
            return repo.resolve_members(group_id)
        finally:
            session.close()

    @staticmethod
    def delete_group(identifier: str) -> bool:
        group = GroupService.resolve_group_identifier(identifier)
        session = get_session()
        try:
            repo = GroupRepository(session)
            return repo.delete_group(group.id) if group.id is not None else False
        finally:
            session.close()

    @staticmethod
    def create_or_get_group(
        name: Optional[str],
        group_type: str,
        transcript_refs: Sequence[str],
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Group:
        transcript_files = GroupService._resolve_transcript_refs(transcript_refs)
        transcript_file_ids = [record.id for record in transcript_files]
        ordered_uuids = [record.uuid for record in transcript_files]
        key = Group.compute_key(ordered_uuids)

        session = get_session()
        try:
            repo = GroupRepository(session)
            existing = repo.get_by_key(key)
            if existing:
                logger.info(
                    "Group already exists, returning existing group for key %s", key
                )
                return existing
            return repo.create_group(
                name=name,
                group_type=group_type,
                transcript_file_ids_ordered=transcript_file_ids,
                description=description,
                metadata=metadata,
            )
        finally:
            session.close()

    @staticmethod
    def validate_transcripts_exist(transcript_refs: Sequence[str]) -> None:
        missing = GroupService._find_missing_transcripts(transcript_refs)
        if missing:
            raise ValueError(f"Transcript files not found: {missing}")

    @staticmethod
    def _resolve_transcript_refs(
        transcript_refs: Sequence[str],
    ) -> List[TranscriptFile]:
        session = get_session()
        try:
            repo = TranscriptFileRepository(session)
            resolved: List[TranscriptFile] = []
            missing: List[str] = []
            for ref in transcript_refs:
                record = GroupService._resolve_single_ref(repo, ref)
                if record is None:
                    missing.append(ref)
                    continue
                resolved.append(record)
            if missing:
                raise ValueError(f"Transcript files not found: {missing}")
            return resolved
        finally:
            session.close()

    @staticmethod
    def _find_missing_transcripts(transcript_refs: Sequence[str]) -> List[str]:
        session = get_session()
        try:
            repo = TranscriptFileRepository(session)
            missing: List[str] = []
            for ref in transcript_refs:
                record = GroupService._resolve_single_ref(repo, ref)
                if record is None:
                    missing.append(ref)
            return missing
        finally:
            session.close()

    @staticmethod
    def _resolve_single_ref(
        repo: TranscriptFileRepository, ref: str
    ) -> Optional[TranscriptFile]:
        if _looks_like_uuid(ref):
            return repo.get_transcript_file_by_uuid(ref)
        if ref.isdigit():
            return repo.get_transcript_file_by_id(int(ref))
        return repo.get_transcript_file_by_path(ref)
