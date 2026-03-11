"""Request types for workflow execution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Literal, Optional


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
    """
    Input for audio preprocessing.

    Precedence contract:
    - ``operation`` controls which phases run:
        "assess"                 — noise assessment + compliance check only; no output file
        "preprocess"             — processing + export only; skips assessment phase
        "assess_and_preprocess"  — assessment then processing + export
    - ``preprocessing_mode`` controls what gets applied within the processing phase:
        "off"      — skip all DSP steps (if combined with assess_and_preprocess, assess
                     still runs but no output file is produced)
        "selected" — apply only steps where preprocessing_decisions[step] is True
        "auto"     — derive decisions from assess_audio_noise suggested_steps (intelligent)
    - ``operation="preprocess"`` combined with ``preprocessing_mode="off"`` is a caller
      error; the workflow raises ValueError rather than silently no-opping.
    - ``config`` carries numeric parameters (LUFS target, cutoffs, strengths) only.
      The user's run-time mode choice lives in ``preprocessing_mode``, not config.

    Request-time modes (preprocessing_mode) are distinct from config-time modes
    (AudioPreprocessingConfig per-step/global). The workflow translates
    preprocessing_mode into a per-step decisions dict for apply_preprocessing();
    see preprocess workflow _derive_decisions() and AudioPreprocessingConfig
    docstring for the bridge.
    """

    input_path: Path
    operation: Literal["assess", "preprocess", "assess_and_preprocess"] = (
        "assess_and_preprocess"
    )
    preprocessing_mode: Literal["off", "selected", "auto"] = "auto"
    output_dir: Optional[Path] = None
    output_format: Literal["wav", "mp3"] = "wav"
    overwrite: bool = False
    config: Optional[Any] = None  # AudioPreprocessingConfig; Any avoids circular import
    preprocessing_decisions: Optional[Dict[str, bool]] = None
    options: Optional[dict] = None  # type: ignore[type-arg]


@dataclass
class MergeRequest:
    """
    Input for audio file merge.

    file_paths must contain at least 2 unique paths, all of which must exist
    and have a supported audio extension.  Default output naming uses the
    first file in the list for the date prefix (e.g. extract_date_prefix on
    file_paths[0]).
    """

    file_paths: list[Path]
    output_dir: Optional[Path] = None
    output_filename: Optional[str] = None
    backup_wavs: bool = True
    overwrite: bool = False


@dataclass
class BatchAnalysisRequest:
    """Input for batch analysis."""

    folder: Path
    analysis_mode: str = "quick"
    selected_modules: Optional[list[str]] = None
    skip_speaker_gate: bool = False
    persist: bool = False
