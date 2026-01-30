"""Repository for TranscriptSet persistence."""

from typing import Any, Dict, List, Optional

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.domain.transcript_set import TranscriptSet as DomainTranscriptSet
from transcriptx.database.models.transcript_set import TranscriptSet, TranscriptSetMember
from transcriptx.database.models.transcript import TranscriptFile

logger = get_logger()


class TranscriptSetRepository:
    def __init__(self, session):
        self.session = session

    def create_transcript_set(
        self,
        name: Optional[str],
        transcript_ids: List[str],
        metadata: Optional[Dict[str, Any]] = None,
        transcript_file_ids: Optional[List[int]] = None,
    ) -> TranscriptSet:
        transcript_set = TranscriptSet(
            name=name,
            transcript_ids=transcript_ids,
            set_metadata=metadata or {},
        )
        self.session.add(transcript_set)
        self.session.flush()

        if transcript_file_ids:
            for order_index, file_id in enumerate(transcript_file_ids):
                member = TranscriptSetMember(
                    set_id=transcript_set.id,
                    transcript_file_id=file_id,
                    order_index=order_index,
                )
                self.session.add(member)

        self.session.commit()
        logger.info(f"✅ Created TranscriptSet {transcript_set.id}")
        return transcript_set

    def get_by_id(self, set_id: int) -> Optional[TranscriptSet]:
        return (
            self.session.query(TranscriptSet)
            .filter(TranscriptSet.id == set_id)
            .first()
        )

    def get_by_uuid(self, set_uuid: str) -> Optional[TranscriptSet]:
        return (
            self.session.query(TranscriptSet)
            .filter(TranscriptSet.uuid == set_uuid)
            .first()
        )

    def get_by_key(self, key: str) -> Optional[TranscriptSet]:
        try:
            candidates = self.session.query(TranscriptSet).all()
            for transcript_set in candidates:
                transcript_ids = transcript_set.transcript_ids or []
                computed = DomainTranscriptSet.compute_key(transcript_ids)
                if computed == key:
                    return transcript_set
            return None
        except Exception as e:
            logger.exception("Failed to lookup TranscriptSet by key: %s", e)
            return None

    def get_by_name(self, name: str) -> Optional[TranscriptSet]:
        return (
            self.session.query(TranscriptSet).filter(TranscriptSet.name == name).first()
        )

    def list_sets(self) -> List[TranscriptSet]:
        return self.session.query(TranscriptSet).order_by(TranscriptSet.id).all()

    def resolve_members(self, transcript_set: TranscriptSet) -> List[TranscriptFile]:
        members = (
            self.session.query(TranscriptSetMember)
            .filter(TranscriptSetMember.set_id == transcript_set.id)
            .order_by(TranscriptSetMember.order_index)
            .all()
        )
        file_ids = [member.transcript_file_id for member in members]
        if not file_ids:
            return []
        return (
            self.session.query(TranscriptFile)
            .filter(TranscriptFile.id.in_(file_ids))
            .all()
        )

    def delete_transcript_set(self, transcript_set: TranscriptSet) -> None:
        self.session.delete(transcript_set)
        self.session.commit()
