"""
TranscriptStore: sole writer for transcript JSON files.
Uses lockfile + atomic write (.tmp then os.replace) + schema stamps.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict

from transcriptx.core.utils.file_lock import FileLock
from transcriptx.core.utils.logger import get_logger

logger = get_logger()

# Metadata keys written on every mutation (for auditing)
_LAST_MODIFIED_BY = "_last_modified_by"
_LAST_MODIFIED_AT = "_last_modified_at"


def _maybe_refresh_metadata(data: Dict[str, Any]) -> None:
    """Recompute derived metadata when configured and segments are present."""
    if not isinstance(data.get("segments"), list):
        return
    try:
        from transcriptx.io.metadata_display_options import get_metadata_config
        from transcriptx.io.transcript_schema import refresh_document_metadata

        if get_metadata_config().auto_refresh_on_write:
            refresh_document_metadata(data)
    except Exception:
        logger.debug("Skipping metadata refresh before transcript write", exc_info=True)


def _stamp_and_write(path: Path, data: Dict[str, Any], reason: str) -> None:
    """Internal: stamp data and atomic write to path (caller must hold lock if needed)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    working = dict(data)
    _maybe_refresh_metadata(working)
    working[_LAST_MODIFIED_BY] = reason
    working[_LAST_MODIFIED_AT] = datetime.now(timezone.utc).isoformat()
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(working, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)


class TranscriptStore:
    """
    Sole writer for transcript JSON files.
    All transcript JSON writes must go through this store (or a service that delegates to it).
    """

    def read(self, path: str | Path) -> Dict[str, Any]:
        """Read transcript JSON (no lock). Raises if file missing or invalid."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(str(path))
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError(f"Transcript at {path} is not a JSON object")
        return data

    def write(
        self,
        path: str | Path,
        data: Dict[str, Any],
        *,
        reason: str = "write",
        timeout: int = 15,
    ) -> None:
        """
        Atomic write: lockfile -> stamp -> json.dump to .tmp -> os.replace.
        Stamps _last_modified_by and _last_modified_at on data.
        """
        path = Path(path)
        with FileLock(path, timeout=timeout):
            _stamp_and_write(path, data, reason)

    def mutate(
        self,
        path: str | Path,
        mutator: Callable[[Dict[str, Any]], None],
        *,
        reason: str = "mutate",
        timeout: int = 15,
    ) -> Dict[str, Any]:
        """
        Read-mutate-write under lock. Returns updated data.
        Acquires lock, reads, calls mutator(data), then atomic write.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(str(path))
        with FileLock(path, timeout=timeout):
            data = self.read(path)
            mutator(data)
            _stamp_and_write(path, data, reason)
        return self.read(path)
