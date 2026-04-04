"""Subject resolution service for the Web UI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from transcriptx.core.pipeline.target_resolver import (
    GroupRef,
    TranscriptRef,
    resolve_analysis_target,
)
from transcriptx.core.store.group_manifest_store import manifest_path_for
from transcriptx.core.domain.group import GroupMember
from transcriptx.web.services.file_service import FileService

SubjectType = Literal["transcript", "group"]


@dataclass(frozen=True)
class SubjectDisplay:
    name: str
    badge: str
    member_count: int


@dataclass(frozen=True)
class ResolvedSubject:
    subject_type: SubjectType
    subject_id: str
    ref: TranscriptRef | GroupRef
    scope: Any
    members: List[GroupMember]
    display: SubjectDisplay


def _is_raw_transcript_path(subject_id: str) -> bool:
    try:
        p = Path(subject_id).expanduser().resolve()
        return p.is_file() and p.suffix.lower() == ".json"
    except Exception:
        return False


class SubjectService:
    @staticmethod
    def resolve_current_subject(
        session_state: Dict[str, Any],
    ) -> Optional[ResolvedSubject]:
        subject_type = session_state.get("subject_type")
        subject_id = session_state.get("subject_id")
        run_id = session_state.get("run_id")
        if subject_type not in ("transcript", "group"):
            return None
        if not subject_id:
            return None

        if subject_type == "transcript":
            if _is_raw_transcript_path(subject_id):
                ref = TranscriptRef(path=str(Path(subject_id).expanduser().resolve()))
                try:
                    scope, members = resolve_analysis_target(ref)
                except Exception:
                    return None
                display = SubjectDisplay(
                    name=scope.display_name,
                    badge="Transcript",
                    member_count=len(members),
                )
                return ResolvedSubject(
                    subject_type=subject_type,
                    subject_id=subject_id,
                    ref=ref,
                    scope=scope,
                    members=members,
                    display=display,
                )

            session_name = subject_id
            if run_id:
                session_name = f"{subject_id}/{run_id}"
            transcript_path = FileService.resolve_transcript_path(session_name)
            if transcript_path is None:
                return None
            ref = TranscriptRef(path=str(transcript_path))
            try:
                scope, members = resolve_analysis_target(ref)
            except Exception:
                return None
            display = SubjectDisplay(
                name=scope.display_name, badge="Transcript", member_count=len(members)
            )
            return ResolvedSubject(
                subject_type=subject_type,
                subject_id=subject_id,
                ref=ref,
                scope=scope,
                members=members,
                display=display,
            )

        group_path = manifest_path_for(subject_id)
        ref = GroupRef(path=str(group_path))
        try:
            scope, members = resolve_analysis_target(ref)
        except Exception:
            return None
        display = SubjectDisplay(
            name=scope.display_name, badge="Group", member_count=len(members)
        )
        return ResolvedSubject(
            subject_type=subject_type,
            subject_id=subject_id,
            ref=ref,
            scope=scope,
            members=members,
            display=display,
        )
