"""Export provenance writer (SSoT)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from transcriptx.services.corrections_studio.schema import ExportProvenance


def write_export_provenance(path: str | Path, provenance: ExportProvenance) -> None:
    """Atomically write provenance JSON next to export artifacts."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    data = provenance.model_dump(mode="json")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
