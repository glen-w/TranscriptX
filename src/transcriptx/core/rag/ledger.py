"""Ingest ledger: track which transcripts are indexed and whether they're stale.

JSONL file per embed model tracking: session_slug, run_id, file_sha, mtime, params.
On transcript admit/correction/delete, ledger entries are invalidated (re-ingested).
"""

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class LedgerEntry:
    """One transcript's ingest status."""

    session_slug: str
    run_id: str
    transcript_path: str
    """Filesystem path to the transcript JSON."""

    file_sha256: str
    """SHA256 of transcript file content at ingest time."""

    file_mtime: float
    """Modification time of transcript file at ingest time."""

    ingested_at: float
    """Timestamp when this entry was created."""

    chunker_version: str
    """Chunker algorithm version (invalidates on change)."""

    embed_model: str
    """Embed model fingerprint (invalidates on model change)."""

    embed_dim: int
    """Embed dimension at ingest time."""

    source: str = "segments"
    """'segments' or 'corrected'."""

    chunks_count: int = 0
    """Number of chunks from this transcript."""

    chunk_start_idx: int = 0
    """First chunk index in global sequence."""

    chunk_end_idx: int = 0
    """Last chunk index in global sequence."""

    error: Optional[str] = None
    """Error message if ingest failed."""

    def is_fresh(
        self,
        current_file_sha: str,
        current_file_mtime: float,
        current_chunker_version: str,
        current_embed_model: str,
    ) -> bool:
        """Check if this entry matches current file state and params."""
        return (
            self.file_sha256 == current_file_sha
            and self.file_mtime == current_file_mtime
            and self.chunker_version == current_chunker_version
            and self.embed_model == current_embed_model
        )


class Ledger:
    """In-memory ledger with JSONL persistence.

    Loads all entries at open(); writes append-only. On re-ingest,
    new entry replaces old (by session_slug/run_id).
    """

    def __init__(self, path: Path):
        """Load ledger from path (or start empty if file doesn't exist)."""
        self.path = path
        self.entries: Dict[tuple[str, str], LedgerEntry] = {}
        self.load()

    def load(self) -> None:
        """Read JSONL ledger file."""
        if not self.path.exists():
            return

        self.entries.clear()
        with open(self.path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    entry = LedgerEntry(**data)
                    key = (entry.session_slug, entry.run_id)
                    self.entries[key] = entry
                except (json.JSONDecodeError, TypeError) as e:
                    # Log and skip malformed lines (P0: simple stderr, P1: observability)
                    print(f"Ledger: skipped malformed line: {e}")

    def add(self, entry: LedgerEntry) -> None:
        """Add or replace an entry and persist."""
        key = (entry.session_slug, entry.run_id)
        self.entries[key] = entry
        self._append_to_file(entry)

    def remove(self, session_slug: str, run_id: str) -> None:
        """Remove an entry (e.g., on transcript delete).

        TODO(P1): Implement rewriting ledger to exclude the entry
        (for now, entries accumulate and are shadowed by newer versions).
        """
        key = (session_slug, run_id)
        if key in self.entries:
            del self.entries[key]

    def get(self, session_slug: str, run_id: str) -> Optional[LedgerEntry]:
        """Fetch entry by (session_slug, run_id)."""
        return self.entries.get((session_slug, run_id))

    def entries_for_session(self, session_slug: str) -> List[LedgerEntry]:
        """All entries for a session (used for index status)."""
        return [
            entry
            for (s, r), entry in self.entries.items()
            if s == session_slug
        ]

    def _append_to_file(self, entry: LedgerEntry) -> None:
        """Append entry as JSONL line."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a") as f:
            f.write(json.dumps(asdict(entry)) + "\n")


def file_sha256(path: Path) -> str:
    """SHA256 of file content."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def file_mtime(path: Path) -> float:
    """Modification time of file (seconds since epoch)."""
    return path.stat().st_mtime
