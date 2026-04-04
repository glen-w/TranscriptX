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
