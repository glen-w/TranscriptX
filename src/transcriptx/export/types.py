"""Public export types and shared constants."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Optional, TypedDict

from transcriptx.web.models.artifact import Artifact

HARD_CAP_BYTES = 2 * 1024 * 1024 * 1024

ChartKind = Literal["static", "dynamic"]


class ExportTextSummary(TypedDict, total=False):
    section_id: str
    title: str
    body: str
    provenance: dict[str, Any]


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


@dataclass(frozen=True)
class ChartExportCard:
    """Renderer-neutral chart card shared by HTML and EPUB exporters."""

    title: str
    meta: str
    kind: ChartKind
    description: Optional[str] = None
    llm_description: Optional[str] = None
    source_path: Optional[Path] = None
    export_rel_path: Path = Path()
    display_relpath: str = ""


@dataclass(frozen=True)
class ChartModuleGroup:
    module_name: str
    anchor_id: str
    cards: tuple[ChartExportCard, ...] = ()


@dataclass(frozen=True)
class TranscriptExportMeta:
    segment_count: int
    speakers: tuple[str, ...]
    duration_seconds: Optional[float] = None
    language: Optional[str] = None


@dataclass(frozen=True)
class ResolvedExportBundle:
    """Selection-scoped inputs shared by HTML and EPUB Overview export indexes."""

    page_title: str
    transcript_data: Optional[dict[str, Any]] = None
    text_summaries: tuple[ExportTextSummary, ...] = ()
    chart_items: tuple[ExportableItem, ...] = ()
    chart_groups: tuple[ChartModuleGroup, ...] = ()
    included_files: tuple[str, ...] = ()
