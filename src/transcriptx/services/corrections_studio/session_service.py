"""CorrectionsStudioSessionService: load/save snapshot, events, index updates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from transcriptx.core.store.corrections_session_store import (
    CorrectionsSessionStore,
    GenerationCommitConflict,
    _last_event_sequence_from_lines,
)
from transcriptx.services.corrections_studio.normalize import (
    normalize_cutover_session_blob,
    session_document_to_persistence,
)
from transcriptx.services.corrections_studio.reconcile import (
    parse_events_jsonl,
    reconcile_snapshot_from_events,
)
from transcriptx.services.corrections_studio.schema import (
    StudioEventEnvelope,
    StudioSessionDocument,
)


@dataclass(frozen=True)
class PersistPreconditions:
    """Optimistic concurrency preconditions for a generation / event batch commit."""

    expected_last_event_sequence: int
    expected_current_generation_id: Optional[int] = None
    expected_transcript_identity_hash: Optional[str] = None
    expected_studio_session_rules_fingerprint: Optional[str] = None
    check_generation_id: bool = False


class CorrectionsStudioSessionService:
    def __init__(self, store: Optional[CorrectionsSessionStore] = None) -> None:
        self._store = store or CorrectionsSessionStore()

    @property
    def store(self) -> CorrectionsSessionStore:
        return self._store

    def load_document(self, session_id: str) -> StudioSessionDocument:
        raw = self._store.find_by_session_id(session_id)
        if not raw:
            raise ValueError(f"Session not found: {session_id}")
        return normalize_cutover_session_blob(raw)

    def load_document_optional(
        self, session_id: str
    ) -> Optional[StudioSessionDocument]:
        try:
            return self.load_document(session_id)
        except ValueError:
            return None

    def last_event_sequence(self, session_id: str) -> int:
        lines = self._store.read_event_lines(session_id)
        return _last_event_sequence_from_lines(lines)

    def next_event_sequence(self, session_id: str) -> int:
        """Peek next sequence (unlocked). Prefer locked allocation via persist_event_batch."""
        last = self.last_event_sequence(session_id)
        return last + 1 if last else 1

    def persist(
        self,
        transcript_path: str,
        doc: StudioSessionDocument,
        event: Optional[StudioEventEnvelope] = None,
    ) -> None:
        data = session_document_to_persistence(doc)
        if event:
            self._store.write_snapshot_and_event_batch(
                transcript_path,
                data,
                [event.model_dump(mode="json")],
                allocate_sequences=True,
            )
        else:
            self._store.write(transcript_path, data)

    def persist_event_batch(
        self,
        transcript_path: str,
        doc: StudioSessionDocument,
        events: List[StudioEventEnvelope],
        *,
        preconditions: Optional[PersistPreconditions] = None,
    ) -> List[StudioEventEnvelope]:
        """
        Persist an ordered event batch and final snapshot under one lock.

        Sequences are allocated while holding the session lock when preconditions
        are provided (or always for multi-event safety).
        """
        if not events:
            data = session_document_to_persistence(doc)
            self._store.write(transcript_path, data)
            return []

        data = session_document_to_persistence(doc)
        expected_last: Optional[int] = None
        expected_gen: Optional[int] = None
        check_gen = False
        if preconditions is not None:
            expected_last = preconditions.expected_last_event_sequence
            expected_gen = preconditions.expected_current_generation_id
            check_gen = preconditions.check_generation_id
            if preconditions.expected_transcript_identity_hash is not None:
                live = self.load_document(doc.session_id)
                if (
                    live.recorded_transcript_identity_hash
                    != preconditions.expected_transcript_identity_hash
                ):
                    raise GenerationCommitConflict(
                        "Transcript identity changed during generation",
                        reason="transcript_identity_conflict",
                    )
            if preconditions.expected_studio_session_rules_fingerprint is not None:
                from transcriptx.services.corrections_studio.generation_manifest import (
                    studio_session_rules_fingerprint,
                )

                live = self.load_document(doc.session_id)
                live_fp = studio_session_rules_fingerprint(live.rules)
                if live_fp != preconditions.expected_studio_session_rules_fingerprint:
                    raise GenerationCommitConflict(
                        "Session rules changed during generation",
                        reason="session_rules_conflict",
                    )

        assigned_dicts = self._store.write_snapshot_and_event_batch(
            transcript_path,
            data,
            [e.model_dump(mode="json") for e in events],
            expected_last_event_sequence=expected_last,
            expected_current_generation_id=expected_gen,
            check_generation_id=check_gen,
            allocate_sequences=True,
        )
        return [StudioEventEnvelope.model_validate(d) for d in assigned_dicts]

    def reconcile_from_events(self, session_id: str) -> StudioSessionDocument:
        lines = self._store.read_event_lines(session_id)
        if not lines:
            return self.load_document(session_id)
        events = parse_events_jsonl(lines)
        if not events:
            return self.load_document(session_id)
        return reconcile_snapshot_from_events(events=events)
