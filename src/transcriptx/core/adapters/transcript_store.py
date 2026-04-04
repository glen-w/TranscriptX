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
