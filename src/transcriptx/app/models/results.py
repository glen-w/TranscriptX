"""Result types for workflow execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

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
    #: Group runs: structured warnings from aggregation / group charts (see aggregation_warnings.json).
    aggregation_warnings: List[Any] = field(default_factory=list)


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
    #: Successful runs only, in processing order (for post-batch action links).
    runs: list[RunSummary] = field(default_factory=list)


@dataclass(frozen=True)
class TranscriptionProviderResult:
    """Result of a single provider subprocess invocation."""

    success: bool
    json_path: Optional[Path]
    output_dir: Path
    returncode: Optional[int]
    stdout_tail: tuple[str, ...]
    stderr_tail: tuple[str, ...]
    duration_seconds: float
    error: Optional[str] = None


@dataclass(frozen=True)
class TranscriptionFileResult:
    """Per-file result within a transcription batch."""

    input_path: Path
    provider_id: str
    success: bool
    created_staged_file: bool
    staged_mp3_path: Optional[Path]
    raw_json_path: Optional[Path]
    imported_json_path: Optional[Path]
    import_success: Optional[bool]
    errors: tuple[str, ...]
    stderr_tail: tuple[str, ...]
    duration_seconds: float


@dataclass
class TranscriptionBatchResult:
    """Summary of a transcription batch run."""

    job_id: str
    success: bool
    file_results: list[TranscriptionFileResult]
    succeeded_count: int
    failed_count: int
    output_dir: Path
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
