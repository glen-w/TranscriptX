"""
Atomic file writer utilities for TranscriptX artifacts.
"""

from __future__ import annotations

import csv
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable, List, Optional


def _ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _atomic_replace(src: Path, dest: Path) -> None:
    """
    Replace destination atomically where possible.
    Uses os.replace for cross-platform atomic replace semantics.
    """
    os.replace(src, dest)


def write_bytes(path: str | Path, data: bytes) -> Path:
    target = Path(path)
    _ensure_parent_dir(target)
    with tempfile.NamedTemporaryFile(delete=False, dir=str(target.parent)) as tmp:
        tmp.write(data)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = Path(tmp.name)
    _atomic_replace(tmp_path, target)
    return target


def write_text(path: str | Path, text: str, encoding: str = "utf-8") -> Path:
    return write_bytes(path, text.encode(encoding))


def write_json(
    path: str | Path, data: Any, indent: int = 2, ensure_ascii: bool = False
) -> Path:
    payload = json.dumps(data, indent=indent, ensure_ascii=ensure_ascii, default=str)
    return write_text(path, payload)


def write_csv(
    path: str | Path,
    rows: Iterable[Iterable[Any]],
    header: Optional[List[str]] = None,
    newline: str = "",
) -> Path:
    target = Path(path)
    _ensure_parent_dir(target)
    with tempfile.NamedTemporaryFile(
        delete=False,
        dir=str(target.parent),
        mode="w",
        newline=newline,
        encoding="utf-8",
    ) as tmp:
        writer = csv.writer(tmp)
        if header:
            writer.writerow(header)
        for row in rows:
            writer.writerow(row)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = Path(tmp.name)
    _atomic_replace(tmp_path, target)
    return target
