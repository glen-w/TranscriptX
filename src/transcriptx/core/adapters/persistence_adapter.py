"""
Persistence adapter interfaces.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from transcriptx.core.utils.logger import get_logger  # type: ignore[import]

logger = get_logger()


class PersistenceAdapter(ABC):
    """Abstract adapter for optional persistence."""

    @abstractmethod
    def persist_transcript(
        self, transcript_path: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def persist_run(self, run_metadata: Dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def persist_artifacts(self, artifacts: Dict[str, Any]) -> None:
        raise NotImplementedError


class NullPersistenceAdapter(PersistenceAdapter):
    """No-op adapter used in stateless mode."""

    def persist_transcript(
        self, transcript_path: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        return None

    def persist_run(self, run_metadata: Dict[str, Any]) -> None:
        return None

    def persist_artifacts(self, artifacts: Dict[str, Any]) -> None:
        return None


class DatabasePersistenceAdapter(PersistenceAdapter):
    """DB-backed adapter for persistence."""

    def __init__(self) -> None:
        self._coordinator = None

    def persist_transcript(
        self, transcript_path: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        try:
            from transcriptx.database.transcript_ingestion import TranscriptIngestionService  # type: ignore[import]

            ingestion = TranscriptIngestionService()
            try:
                ingestion.ingest_transcript(transcript_path, store_segments=False)
            finally:
                ingestion.close()
        except Exception as exc:
            logger.warning(f"Failed to persist transcript metadata: {exc}")

    def persist_run(self, run_metadata: Dict[str, Any]) -> None:
        logger.debug(
            "persist_run called with metadata keys: %s", list(run_metadata.keys())
        )

    def persist_artifacts(self, artifacts: Dict[str, Any]) -> None:
        logger.debug("persist_artifacts called with keys: %s", list(artifacts.keys()))
