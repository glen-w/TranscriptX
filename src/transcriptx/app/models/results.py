"""Result types for workflow execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from transcriptx.core.audio.types import AudioAssessment, AudioCompliance


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
    errors: list[str] = field(default_factory=list)


@dataclass
class PreprocessResult:
    """
    Result of audio preprocessing.

    compliance reflects the source file only (v1).
    Output compliance is not re-checked after export.
    """

    success: bool
    output_path: Optional[Path] = None
    applied_steps: list[str] = field(default_factory=list)
    assessment: Optional[AudioAssessment] = None
    compliance: Optional[AudioCompliance] = None
    duration_seconds: Optional[float] = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class MergeResult:
    """
    Result of audio file merge.

    warnings carries non-fatal notices (e.g. backup failed but merge succeeded).
    errors carries fatal problems (merge did not complete).
    """

    success: bool
    output_path: Optional[Path] = None
    files_merged: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class BatchAnalysisResult:
    """Result of batch analysis."""

    success: bool
    transcript_count: int
    errors: list[str] = field(default_factory=list)
    message: Optional[str] = None
