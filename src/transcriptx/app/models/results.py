"""Result types for workflow execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class RunSummary:
    """Run identity contract. Manifest is authoritative when present."""

    run_dir: Path
    transcript_path: Path
    run_id: str
    created_at: datetime
    selected_modules: list[str]
    profile_name: Optional[str] = None
    manifest_path: Path = Path()
    status: str = "unknown"
    duration_seconds: Optional[float] = None
    warnings_count: Optional[int] = None


@dataclass
class AnalysisResult:
    """Result of single-transcript analysis."""

    success: bool
    run_dir: Path
    manifest_path: Path
    modules_executed: list[str]
    warnings: list[str]
    errors: list[str]
    duration_seconds: Optional[float] = None
    status: str = "completed"


@dataclass
class SpeakerIdentificationResult:
    """Result of speaker identification."""

    success: bool
    updated_paths: list[Path]
    speakers_identified: int
    errors: list[str] = ()


@dataclass
class PreprocessResult:
    """Result of audio preprocessing. Details TBD in Phase 5."""

    success: bool
    output_path: Optional[Path] = None
    errors: list[str] = ()


@dataclass
class BatchAnalysisResult:
    """Result of batch analysis."""

    success: bool
    transcript_count: int
    errors: list[str] = ()
    message: Optional[str] = None
