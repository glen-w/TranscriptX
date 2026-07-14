"""Crash-safe staged JSON / bytes persistence for managed rename."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


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


def write_json_atomic(path: Path, payload: dict[str, Any], *, indent: int = 2) -> None:
    """Serialize JSON and persist with crash-safe staged write."""
    text = json.dumps(payload, ensure_ascii=False, indent=indent) + "\n"
    write_bytes_atomic(path, text.encode("utf-8"))


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
