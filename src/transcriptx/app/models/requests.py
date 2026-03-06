"""Request types for workflow execution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class AnalysisRequest:
    """Input for single-transcript analysis."""

    transcript_path: Path
    mode: str = "quick"
    modules: Optional[list[str]] = None
    profile: Optional[str] = None
    skip_speaker_mapping: bool = True
    output_dir: Optional[Path] = None
    run_label: Optional[str] = None
    persist: bool = False
    include_unidentified_speakers: bool = False


@dataclass
class SpeakerIdentificationRequest:
    """Input for speaker identification."""

    transcript_paths: list[Path]
    overwrite: bool = False
    skip_rename: bool = False


@dataclass
class PreprocessRequest:
    """Input for audio preprocessing. Details TBD in Phase 5."""

    input_path: Path
    operation: str  # convert, merge, compress, preprocess
    output_path: Optional[Path] = None
    options: Optional[dict] = None


@dataclass
class BatchAnalysisRequest:
    """Input for batch analysis."""

    folder: Path
    analysis_mode: str = "quick"
    selected_modules: Optional[list[str]] = None
    skip_speaker_gate: bool = False
    persist: bool = False
