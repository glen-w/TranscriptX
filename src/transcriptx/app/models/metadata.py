"""Clean metadata shapes for controllers, separate from display formatting."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class TranscriptMetadata:
    """Clean data shape for transcript metadata. Not display-oriented."""

    path: Path
    base_name: str
    duration_seconds: Optional[float] = None
    speaker_count: Optional[int] = None
    named_speaker_count: Optional[int] = None
    has_analysis_outputs: bool = False
    has_speaker_map: bool = False
    linked_run_dirs: list[Path] = field(default_factory=list)
    # Populated when segments load; used by web dropdown formatters (Run Analysis, etc.).
    segment_count: Optional[int] = None
    speaker_map_status: str = "none"
    unidentified_speaker_count: int = 0
    ignored_speaker_count: int = 0
