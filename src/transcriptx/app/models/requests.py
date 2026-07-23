"""Request types for workflow execution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Literal, Mapping, Optional

if TYPE_CHECKING:
    from transcriptx.core.analysis.llm_support.model_selection import LlmModelSelection


def _validate_llm_custom_qa_questions_field(raw: Any) -> None:
    """Reject malformed custom-QA request payloads at construction time."""
    if raw is None:
        return
    from transcriptx.core.analysis.llm_custom_qa.request_questions import (
        coerce_request_questions,
    )

    coerce_request_questions(
        raw,
        field_present=True,
        max_questions=50,
        max_question_chars=2000,
        max_total_question_chars=20000,
    )


@dataclass
class AnalysisRequest:
    """Input for single-transcript analysis."""

    transcript_path: Path
    mode: str = "quick"
    modules: Optional[list[str]] = None
    profile: Optional[str] = None
    # UI launch preset: quick | balanced | thorough | custom (optional; persisted on run)
    analysis_preset: Optional[str] = None
    output_dir: Optional[Path] = None
    run_label: Optional[str] = None
    persist: bool = False
    include_unidentified_speakers: bool = False
    llm_model_selection: LlmModelSelection | Mapping[str, Any] | None = None
    # None/omitted → library; [] → explicit empty run; list[str]|list[dict] → request
    llm_custom_qa_questions: list[str] | list[dict[str, Any]] | None = None

    def __post_init__(self) -> None:
        _validate_llm_custom_qa_questions_field(self.llm_custom_qa_questions)


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
class GroupAnalysisRequest:
    """Input for group-level analysis (all members + aggregation)."""

    group_uuid: str
    mode: str = "quick"
    modules: Optional[list[str]] = None
    profile: Optional[str] = None
    analysis_preset: Optional[str] = None
    include_unidentified_speakers: bool = False
    output_dir: Optional[Path] = None
    persist: bool = False
    llm_model_selection: LlmModelSelection | Mapping[str, Any] | None = None
    llm_custom_qa_questions: list[str] | list[dict[str, Any]] | None = None

    def __post_init__(self) -> None:
        _validate_llm_custom_qa_questions_field(self.llm_custom_qa_questions)


@dataclass
class BatchAnalysisRequest:
    """Input for batch analysis. Provide either transcript_paths or folder."""

    transcript_paths: Optional[list[Path]] = None
    folder: Optional[Path] = None
    analysis_mode: str = "quick"
    selected_modules: Optional[list[str]] = None
    analysis_preset: Optional[str] = None
    persist: bool = False
    llm_model_selection: LlmModelSelection | Mapping[str, Any] | None = None
    llm_custom_qa_questions: list[str] | list[dict[str, Any]] | None = None

    def __post_init__(self) -> None:
        _validate_llm_custom_qa_questions_field(self.llm_custom_qa_questions)


@dataclass(frozen=True)
class TranscriptionConversionOptions:
    """ffmpeg MP3 export settings for transcription staging."""

    codec: str = "libmp3lame"
    bitrate: str = "128k"
    channels: int = 2
    sample_rate: int = 0  # 0 → omit -ar
    force_reencode: bool = False


@dataclass(frozen=True)
class TranscriptionOptions:
    """Per-run transcription settings (no secrets)."""

    provider_id: str
    model: str
    language: str
    diarize: bool
    timeout_seconds: int = 0


@dataclass
class TranscriptionRequest:
    """Input for integrated transcription workflow."""

    input_paths: list[Path]
    transcription_options: TranscriptionOptions
    conversion_options: TranscriptionConversionOptions
    output_dir: Optional[Path] = None
    import_into_library: bool = True
    overwrite_import: bool = False
    keep_intermediates: bool = False
