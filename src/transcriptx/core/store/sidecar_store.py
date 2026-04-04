"""Atomic storage for speaker-mapping sidecar files."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from transcriptx.core.utils.file_lock import FileLock
from transcriptx.core.utils.logger import get_logger

logger = get_logger()


def _atomic_write(path: Path, data: Dict[str, Any]) -> None:
    """Write JSON atomically via .tmp + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)


class SidecarStore:
    """Sole storage layer for speaker-mapping sidecar JSON files."""

    def read(self, path: str | Path) -> Optional[Dict[str, Any]]:
        """Return raw sidecar JSON, or None when the file does not exist."""
        path = Path(path)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError(f"Sidecar at {path} is not a JSON object")
        return data

    def write(
        self,
        path: str | Path,
        data: Dict[str, Any],
        *,
        reason: str = "write",
        timeout: int = 15,
    ) -> None:
        """Write sidecar atomically under a file lock."""
        path = Path(path)
        with FileLock(path, timeout=timeout):
            _atomic_write(path, dict(data))
        logger.debug("Wrote sidecar %s for reason=%s", path, reason)

    def mutate(
        self,
        path: str | Path,
        mutator: Callable[[Dict[str, Any]], None],
        *,
        reason: str = "mutate",
        timeout: int = 15,
    ) -> Dict[str, Any]:
        """Read-modify-write the sidecar. Creates the file on first write."""
        path = Path(path)
        with FileLock(path, timeout=timeout):
            current = self.read(path) or {}
            mutator(current)
            _atomic_write(path, current)
        logger.debug("Mutated sidecar %s for reason=%s", path, reason)
        return current
