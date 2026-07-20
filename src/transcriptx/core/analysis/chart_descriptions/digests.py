"""SHA helpers for chart description generations."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


@dataclass(frozen=True)
class GenerationDigests:
    inventory_snapshot_sha256: str
    chart_set: str
    prompt_version: str
    model: str
    options_sha256: str

    def as_dict(self) -> dict[str, str]:
        return {
            "inventory_snapshot_sha256": self.inventory_snapshot_sha256,
            "chart_set": self.chart_set,
            "prompt_version": self.prompt_version,
            "model": self.model,
            "options_sha256": self.options_sha256,
        }
