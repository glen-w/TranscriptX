"""
Adapters for optional persistence and storage.
"""

from .persistence_adapter import (
    PersistenceAdapter,
    NullPersistenceAdapter,
    DatabasePersistenceAdapter,
)
from .transcript_store import (
    TranscriptStore,
    FileTranscriptStore,
    DatabaseTranscriptStore,
)

__all__ = [
    "PersistenceAdapter",
    "NullPersistenceAdapter",
    "DatabasePersistenceAdapter",
    "TranscriptStore",
    "FileTranscriptStore",
    "DatabaseTranscriptStore",
]
