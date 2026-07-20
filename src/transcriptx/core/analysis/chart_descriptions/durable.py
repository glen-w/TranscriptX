"""Durable writes — reuse group synthesis atomic helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from transcriptx.core.analysis.group_llm_synthesis.durable import (
    write_bytes_durable,
    write_json_durable,
)

__all__ = ["write_json_durable", "write_bytes_durable", "copy_file_durable"]


def copy_file_durable(src: Path, dest: Path) -> None:
    data = Path(src).read_bytes()
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_bytes_durable(dest, data)
