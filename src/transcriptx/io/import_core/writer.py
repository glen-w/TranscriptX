"""Writers for canonical and atomic transcript persistence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

from transcriptx.core.store import TranscriptStore


class CanonicalWriter(Protocol):
    def write(
        self,
        target_path: Path,
        document: Mapping[str, Any],
        *,
        overwrite: bool = False,
    ) -> Path: ...


@dataclass(frozen=True)
class AtomicTranscriptWriter:
    """Writer contract: write atomically or fail with no partial visibility."""

    reason: str = "import"

    def write(
        self,
        target_path: Path,
        document: Mapping[str, Any],
        *,
        overwrite: bool = False,
    ) -> Path:
        if target_path.exists() and not overwrite:
            raise FileExistsError(f"Canonical artifact already exists: {target_path}")
        TranscriptStore().write(target_path, dict(document), reason=self.reason)
        return target_path
