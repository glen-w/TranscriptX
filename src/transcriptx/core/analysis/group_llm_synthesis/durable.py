"""Durable JSON writes — shared helper wrapping ``transcriptx.io.atomic_json``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from transcriptx.io.atomic_json import write_bytes_atomic, write_json_atomic

__all__ = ["write_json_durable", "write_bytes_durable"]


def write_json_durable(path: Path, payload: Any, *, indent: int | None = 2) -> None:
    """Flush + fsync staged file, os.replace, fsync parent directory."""
    write_json_atomic(Path(path), payload, indent=indent)


def write_bytes_durable(path: Path, data: bytes) -> None:
    write_bytes_atomic(Path(path), data)
