"""Crash-safe staged JSON / bytes persistence (shared IO primitive)."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from transcriptx.core.utils.file_lock import FileLock

# Process-local locks keyed by resolved path string. Acquire these BEFORE FileLock.
_PROCESS_LOCKS: dict[str, threading.Lock] = {}
_PROCESS_LOCKS_GUARD = threading.Lock()


def _process_lock_for(path: Path) -> threading.Lock:
    key = str(path.resolve()) if path.exists() else str(path.absolute())
    with _PROCESS_LOCKS_GUARD:
        lock = _PROCESS_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _PROCESS_LOCKS[key] = lock
        return lock


@contextmanager
def locked_path(path: Path, *, timeout: float = 30.0) -> Iterator[Path]:
    """Acquire process-local lock then FileLock (mandatory order)."""
    path = Path(path)
    proc = _process_lock_for(path)
    with proc:
        with FileLock(path, timeout=timeout, blocking=True):
            yield path


def write_bytes_atomic(path: Path, data: bytes) -> None:
    """Write bytes via temp sibling → fsync → replace → best-effort parent fsync."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temp), str(path))
        _fsync_dir(path.parent)
    finally:
        if temp.exists():
            try:
                temp.unlink()
            except OSError:
                pass


def write_bytes_atomic_locked(path: Path, data: bytes, *, timeout: float = 30.0) -> None:
    """Same as write_bytes_atomic but under process lock then FileLock."""
    with locked_path(path, timeout=timeout):
        write_bytes_atomic(path, data)


def write_json_atomic(path: Path, payload: dict[str, Any], *, indent: int = 2) -> None:
    """Serialize JSON and persist with crash-safe staged write."""
    text = json.dumps(payload, ensure_ascii=False, indent=indent) + "\n"
    write_bytes_atomic(path, text.encode("utf-8"))


def write_json_atomic_locked(
    path: Path, payload: dict[str, Any], *, indent: int = 2, timeout: float = 30.0
) -> None:
    """Serialize JSON under process lock then FileLock."""
    text = json.dumps(payload, ensure_ascii=False, indent=indent) + "\n"
    write_bytes_atomic_locked(path, text.encode("utf-8"), timeout=timeout)


def _fsync_dir(directory: Path) -> None:
    try:
        fd = os.open(str(directory), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)
