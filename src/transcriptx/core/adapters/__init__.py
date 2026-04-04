"""Adapters for optional persistence and storage."""

from .persistence_adapter import PersistenceAdapter, NullPersistenceAdapter
from .transcript_store import TranscriptStore, FileTranscriptStore

__all__ = [
    "PersistenceAdapter",
    "NullPersistenceAdapter",
    "TranscriptStore",
    "FileTranscriptStore",
]
