"""Public export types and shared constants."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, TypedDict

from transcriptx.web.models.artifact import Artifact

HARD_CAP_BYTES = 2 * 1024 * 1024 * 1024


@dataclass(frozen=True)
class ChartsExportResult:
    bytes: bytes
    filename: str
    exported_count: int
    omitted_count: int
    module_count: int


@dataclass(frozen=True)
class ExportableItem:
    artifact: Artifact
    source_path: Path
    export_rel_path: Path
    size_bytes: int
    description: Optional[str] = None
    llm_description: Optional[str] = None


class ExportTextSummary(TypedDict, total=False):
    section_id: str
    title: str
    body: str
    provenance: dict[str, Any]
