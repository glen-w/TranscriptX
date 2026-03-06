"""Repository for Group persistence."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import delete

from transcriptx.core.domain.group import Group as DomainGroup
from transcriptx.core.utils.logger import get_logger
from transcriptx.database.models.group import Group as GroupModel, GroupMember
from transcriptx.database.models.transcript import TranscriptFile
from .base import BaseRepository

logger = get_logger()


class GroupRepository(BaseRepository):
    def _resolve_transcript_files_ordered(
        self, transcript_file_ids_ordered: List[int]
    ) -> List[TranscriptFile]:
        if not transcript_file_ids_ordered:
            return []
        records = (
            self.session.query(TranscriptFile)
            .filter(TranscriptFile.id.in_(transcript_file_ids_ordered))
            .all()
        )
        record_map = {record.id: record for record in records}
        ordered_records: List[TranscriptFile] = []
        missing: List[int] = []
        for file_id in transcript_file_ids_ordered:
            record = record_map.get(file_id)
            if record is None:
                missing.append(file_id)
                continue
            ordered_records.append(record)
        if missing:
            raise ValueError(f"Transcript files not found for IDs: {missing}")
        return ordered_records

    def _to_domain(
        self,
        model: GroupModel,
        ordered_members: Optional[List[TranscriptFile]] = None,
    ) -> DomainGroup:
        members = ordered_members or self.resolve_members(model.id)
        transcript_file_uuids = [record.uuid for record in members]
        return DomainGroup(
            id=model.id,
            uuid=model.uuid,
            key=model.key,
            name=model.name,
            type=model.type,
            description=model.description,
            metadata=dict(model.metadata_json or {}),
            transcript_file_uuids=transcript_file_uuids,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def create_group(
        self,
        name: Optional[str],
        group_type: str,
        transcript_file_ids_ordered: List[int],
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DomainGroup:
        ordered_records = self._resolve_transcript_files_ordered(
            transcript_file_ids_ordered
        )
        ordered_uuids = [record.uuid for record in ordered_records]
        key = DomainGroup.compute_key(ordered_uuids)

        group = GroupModel(
            name=name,
            type=group_type,
            key=key,
            description=description,
            metadata_json=metadata or {},
        )
        self.session.add(group)
        self.session.flush()

        for position, record in enumerate(ordered_records):
            member = GroupMember(
                group_id=group.id,
                transcript_file_id=record.id,
                position=position,
            )
            self.session.add(member)

        self.session.commit()
        logger.info("✅ Created group %s", group.uuid)
        return self._to_domain(group, ordered_records)

    def get_by_id(self, group_id: int) -> Optional[DomainGroup]:
        model = self.session.query(GroupModel).filter(GroupModel.id == group_id).first()
        if model is None:
            return None
        return self._to_domain(model)

    def get_by_uuid(self, group_uuid: str) -> Optional[DomainGroup]:
        model = (
            self.session.query(GroupModel).filter(GroupModel.uuid == group_uuid).first()
        )
        if model is None:
            return None
        return self._to_domain(model)

    def get_by_key(self, key: str) -> Optional[DomainGroup]:
        model = self.session.query(GroupModel).filter(GroupModel.key == key).first()
        if model is None:
            return None
        return self._to_domain(model)

    def get_by_name(self, name: str) -> Optional[DomainGroup]:
        model = self.session.query(GroupModel).filter(GroupModel.name == name).first()
        if model is None:
            return None
        return self._to_domain(model)

    def list_by_name(self, name: str) -> List[DomainGroup]:
        models = self.session.query(GroupModel).filter(GroupModel.name == name).all()
        return [self._to_domain(model) for model in models]

    def list_groups(self, group_type: Optional[str] = None) -> List[DomainGroup]:
        query = self.session.query(GroupModel)
        if group_type:
            query = query.filter(GroupModel.type == group_type)
        models = query.order_by(GroupModel.updated_at.desc()).all()
        return [self._to_domain(model) for model in models]

    def resolve_members(self, group_id: int) -> List[TranscriptFile]:
        return (
            self.session.query(TranscriptFile)
            .join(GroupMember, GroupMember.transcript_file_id == TranscriptFile.id)
            .filter(GroupMember.group_id == group_id)
            .order_by(GroupMember.position)
            .all()
        )

    def rename_group(self, group_id: int, name: str) -> Optional[DomainGroup]:
        model = self.session.query(GroupModel).filter(GroupModel.id == group_id).first()
        if model is None:
            return None
        model.name = name
        self.session.commit()
        return self._to_domain(model)

    def update_group_metadata(
        self, group_id: int, metadata: Dict[str, Any]
    ) -> Optional[DomainGroup]:
        model = self.session.query(GroupModel).filter(GroupModel.id == group_id).first()
        if model is None:
            return None
        model.metadata_json = metadata
        self.session.commit()
        return self._to_domain(model)

    def update_membership(
        self, group_id: int, transcript_file_ids_ordered: List[int]
    ) -> Optional[DomainGroup]:
        model = self.session.query(GroupModel).filter(GroupModel.id == group_id).first()
        if model is None:
            return None

        ordered_records = self._resolve_transcript_files_ordered(
            transcript_file_ids_ordered
        )
        ordered_uuids = [record.uuid for record in ordered_records]
        model.key = DomainGroup.compute_key(ordered_uuids)

        self.session.execute(
            delete(GroupMember).where(GroupMember.group_id == group_id)
        )
        for position, record in enumerate(ordered_records):
            self.session.add(
                GroupMember(
                    group_id=group_id,
                    transcript_file_id=record.id,
                    position=position,
                )
            )

        self.session.commit()
        return self._to_domain(model, ordered_records)

    def delete_group(self, group_id: int) -> bool:
        model = self.session.query(GroupModel).filter(GroupModel.id == group_id).first()
        if model is None:
            return False
        self.session.delete(model)
        self.session.commit()
        return True
