"""
Subject resolution service for the Web UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Literal, Dict, Any, List

from transcriptx.core.pipeline.target_resolver import (
    TranscriptRef,
    GroupRef,
    resolve_analysis_target,
)
from transcriptx.database.models.transcript import TranscriptFile
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
    members: List[TranscriptFile]
    display: SubjectDisplay


class SubjectService:
    """Resolve current subject from session state."""

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

        ref = GroupRef(group_uuid=subject_id)
        try:
            scope, members = resolve_analysis_target(ref)
        except Exception:
            return None
        display = SubjectDisplay(
            name=scope.display_name,
            badge="Group",
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
