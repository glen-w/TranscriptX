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


def _fsync_dir(path: Path) -> None:
    """Best-effort fsync of a directory after rename (POSIX)."""
    try:
        fd = os.open(str(path), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _atomic_replace(src: Path, dest: Path) -> None:
    """
    Replace destination atomically where possible.
    Uses os.replace for cross-platform atomic replace semantics.
    """
    os.replace(src, dest)
    _fsync_dir(dest.parent)


def write_bytes(path: str | Path, data: bytes) -> Path:
    target = Path(path)
    _ensure_parent_dir(target)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, dir=str(target.parent)) as tmp:
            tmp.write(data)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = Path(tmp.name)
        _atomic_replace(tmp_path, target)
        tmp_path = None
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
    return target


def write_text(path: str | Path, text: str, encoding: str = "utf-8") -> Path:
    return write_bytes(path, text.encode(encoding))


def write_json(
    path: str | Path,
    data: Any,
    indent: int = 2,
    ensure_ascii: bool = False,
    *,
    allow_nan: bool = True,
    default: Any = str,
) -> Path:
    """Serialize JSON and write atomically.

    For telemetry / strict contracts, pass ``allow_nan=False`` and ``default=None``
    so non-JSON values fail loudly instead of being stringified.
    """
    dump_kwargs: dict[str, Any] = {
        "indent": indent,
        "ensure_ascii": ensure_ascii,
        "allow_nan": allow_nan,
    }
    if default is not None:
        dump_kwargs["default"] = default
    payload = json.dumps(data, **dump_kwargs)
    return write_text(path, payload)


def write_jsonl(
    path: str | Path, rows: Iterable[Any], ensure_ascii: bool = False
) -> Path:
    lines = [json.dumps(row, ensure_ascii=ensure_ascii, default=str) for row in rows]
    payload = "\n".join(lines)
    if payload:
        payload += "\n"
    return write_text(path, payload)


def write_csv(
    path: str | Path,
    rows: Iterable[Iterable[Any]],
    header: Optional[List[str]] = None,
    newline: str = "",
) -> Path:
    target = Path(path)
    _ensure_parent_dir(target)
    tmp_path: Path | None = None
    try:
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
        tmp_path = None
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
    return target
