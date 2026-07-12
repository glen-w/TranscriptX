"""Subject resolution service for the Web UI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence

from transcriptx.core.pipeline.target_resolver import (
    GroupRef,
    TranscriptRef,
    resolve_analysis_target,
)
from transcriptx.core.store.group_manifest_store import manifest_path_for
from transcriptx.core.domain.group import GroupMember
from transcriptx.web.services.file_service import FileService
from transcriptx.web.services.transcript_context_resolver import (
    SessionResolver,
    paths_match,
    resolve_transcript_context,
)

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

    @staticmethod
    def set_transcript_context_from_path(
        session_state: Dict[str, Any],
        transcript_path: str | Path,
        *,
        linked_run_dirs: Sequence[str | Path] | None = None,
        slug_hint: str | None = None,
        latest_run_hint: str | None = None,
        session_resolver: SessionResolver | None = None,
    ) -> None:
        """Write canonical transcript context; never persists legacy path keys."""
        session_state.pop("selected_transcript_path", None)
        resolution = resolve_transcript_context(
            transcript_path,
            linked_run_dirs=linked_run_dirs,
            slug_hint=slug_hint,
            latest_run_hint=latest_run_hint,
            session_resolver=session_resolver,
        )
        session_state["subject_type"] = "transcript"
        session_state["subject_id"] = resolution.subject_id
        session_state["run_id"] = resolution.run_id

    @staticmethod
    def current_transcript_path(session_state: Dict[str, Any]) -> str | None:
        """Cheap read-only path from canonical subject; no discovery I/O."""
        subject = SubjectService.resolve_current_subject(session_state)
        if subject is None or subject.subject_type != "transcript":
            return None
        return str(subject.ref.path)

    @staticmethod
    def index_in_path_options(session_state: Dict[str, Any], options: list[str]) -> int:
        """Return 0-based Streamlit selectbox index (0 = placeholder)."""
        current = SubjectService.current_transcript_path(session_state)
        if not current or not options:
            return 0
        for index, option in enumerate(options):
            if paths_match(option, current):
                return index + 1
        return 0
