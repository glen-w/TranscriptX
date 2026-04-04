"""CorrectionsStudioSessionService: load/save snapshot, events, index updates."""

from __future__ import annotations

import json
from typing import Optional

from transcriptx.core.store.corrections_session_store import CorrectionsSessionStore
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

    def next_event_sequence(self, session_id: str) -> int:
        lines = self._store.read_event_lines(session_id)
        m = 0
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                m = max(m, int(d.get("event_sequence", 0)))
            except Exception:
                continue
        return m + 1 if m else 1

    def persist(
        self,
        transcript_path: str,
        doc: StudioSessionDocument,
        event: Optional[StudioEventEnvelope] = None,
    ) -> None:
        data = session_document_to_persistence(doc)
        if event:
            self._store.write_and_append_event(
                transcript_path, data, event.model_dump(mode="json")
            )
        else:
            self._store.write(transcript_path, data)

    def reconcile_from_events(self, session_id: str) -> StudioSessionDocument:
        lines = self._store.read_event_lines(session_id)
        if not lines:
            return self.load_document(session_id)
        events = parse_events_jsonl(lines)
        if not events:
            return self.load_document(session_id)
        return reconcile_snapshot_from_events(events=events)
