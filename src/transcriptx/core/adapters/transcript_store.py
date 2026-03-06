"""
Transcript storage adapters.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class TranscriptStore(ABC):
    """Abstract interface for optional transcript storage."""

    @abstractmethod
    def store(
        self, transcript_path: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def lookup(self, transcript_key: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError


class FileTranscriptStore(TranscriptStore):
    """No-op store for file-based canonical transcripts."""

    def store(
        self, transcript_path: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        return None

    def lookup(self, transcript_key: str) -> Optional[Dict[str, Any]]:
        return None


class DatabaseTranscriptStore(TranscriptStore):
    """DB-backed transcript store (metadata only)."""

    def store(
        self, transcript_path: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        from transcriptx.database.transcript_ingestion import TranscriptIngestionService  # type: ignore[import]

        ingestion = TranscriptIngestionService()
        try:
            ingestion.ingest_transcript(transcript_path, store_segments=False)
        finally:
            ingestion.close()

    def lookup(self, transcript_key: str) -> Optional[Dict[str, Any]]:
        from transcriptx.database import get_session  # type: ignore[import]
        from transcriptx.database.models import TranscriptFile  # type: ignore[import]

        session = get_session()
        try:
            transcript = (
                session.query(TranscriptFile)
                .filter(TranscriptFile.transcript_content_hash == transcript_key)
                .first()
            )
            if not transcript:
                return None
            return {
                "id": transcript.id,
                "file_path": transcript.file_path,
                "transcript_content_hash": transcript.transcript_content_hash,
                "duration_seconds": transcript.duration_seconds,
                "segment_count": transcript.segment_count,
                "speaker_count": transcript.speaker_count,
            }
        finally:
            session.close()
