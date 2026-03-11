"""
Audio preprocessing workflow. No CLI, UI, or formatting concerns.

Phases (total=5 for progress snapshot):
    validating → assessing → preprocessing → exporting → finalizing

Precedence contract (see PreprocessRequest docstring for full details):
    operation controls which phases execute.
    preprocessing_mode controls what DSP steps run within the processing phase.
    operation="preprocess" + preprocessing_mode="off" raises ValueError.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, Optional

from transcriptx.app.models.requests import PreprocessRequest
from transcriptx.app.models.results import PreprocessResult
from transcriptx.app.progress import NullProgress, ProgressCallback
from transcriptx.core.audio.preprocessing import (
    PYDUB_AVAILABLE,
    apply_preprocessing,
    assess_audio_noise,
    check_audio_compliance,
)
from transcriptx.core.audio.types import AudioAssessment, AudioCompliance
from transcriptx.core.utils.logger import get_logger

logger = get_logger()

# Supported input formats for error messaging
_SUPPORTED_FORMATS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma"}


def run_preprocess(
    request: PreprocessRequest,
    progress: ProgressCallback | None = None,
) -> PreprocessResult:
    """
    Run audio preprocessing (assess, process, or both).

    Returns a PreprocessResult on both success and handled failure so callers
    never need to catch exceptions for expected error cases.  Unexpected
    exceptions propagate and should be caught by the controller.
    """
    if progress is None:
        progress = NullProgress()

    t0 = time.time()

    # ------------------------------------------------------------------
    # Phase 1: Validate
    # ------------------------------------------------------------------
    progress.on_stage_start("validating")

    if not PYDUB_AVAILABLE:
        progress.on_stage_complete("validating")
        return PreprocessResult(
            success=False,
            errors=["pydub is not installed. Install it to use audio preprocessing."],
        )

    if not request.input_path.exists():
        progress.on_stage_complete("validating")
        return PreprocessResult(
            success=False,
            errors=[f"Input file not found: {request.input_path}"],
        )

    suffix = request.input_path.suffix.lower()
    if suffix not in _SUPPORTED_FORMATS:
        progress.on_stage_complete("validating")
        return PreprocessResult(
            success=False,
            errors=[
                f"Unsupported format '{suffix}'. "
                f"Supported: {', '.join(sorted(_SUPPORTED_FORMATS))}"
            ],
        )

    if request.operation == "preprocess" and request.preprocessing_mode == "off":
        progress.on_stage_complete("validating")
        return PreprocessResult(
            success=False,
            errors=[
                "operation='preprocess' is incompatible with preprocessing_mode='off'. "
                "Use operation='assess' or choose a mode other than 'off'."
            ],
        )

    progress.on_log(f"Validated input: {request.input_path.name}", level="info")
    progress.on_stage_complete("validating")

    # ------------------------------------------------------------------
    # Phase 2: Assess (if requested)
    # ------------------------------------------------------------------
    assessment: Optional[AudioAssessment] = None
    compliance: Optional[AudioCompliance] = None

    if request.operation in ("assess", "assess_and_preprocess"):
        progress.on_stage_start("assessing")
        progress.on_log("Running noise assessment…", level="info")

        assessment = assess_audio_noise(request.input_path)
        compliance = check_audio_compliance(request.input_path, request.config)

        noise_level = assessment.get("noise_level", "unknown")
        suggestions = assessment.get("suggested_steps", [])
        progress.on_log(
            f"Noise level: {noise_level} — suggested steps: {suggestions or 'none'}",
            level="info",
        )
        progress.on_stage_complete("assessing")
    else:
        # Emit the assessing phase as a no-op so the total phase count stays
        # consistent (5) regardless of which operations are requested.
        progress.on_stage_start("assessing")
        progress.on_stage_complete("assessing")

    # ------------------------------------------------------------------
    # If mode is "off" (or assess-only), stop here — no output file
    # ------------------------------------------------------------------
    if request.operation == "assess" or request.preprocessing_mode == "off":
        progress.on_stage_start("preprocessing")
        progress.on_stage_complete("preprocessing")
        progress.on_stage_start("exporting")
        progress.on_stage_complete("exporting")
        progress.on_stage_start("finalizing")
        progress.on_stage_complete("finalizing")
        return PreprocessResult(
            success=True,
            assessment=assessment,
            compliance=compliance,
            duration_seconds=time.time() - t0,
        )

    # ------------------------------------------------------------------
    # Phase 3: Preprocess
    # ------------------------------------------------------------------
    progress.on_stage_start("preprocessing")

    try:
        from pydub import AudioSegment  # type: ignore[import]

        audio = AudioSegment.from_file(str(request.input_path))
    except Exception as e:
        progress.on_stage_complete("preprocessing")
        return PreprocessResult(
            success=False,
            assessment=assessment,
            compliance=compliance,
            errors=[f"Failed to load audio file: {e}"],
            duration_seconds=time.time() - t0,
        )

    from transcriptx.core.utils.config import get_config

    config = request.config or get_config().audio_preprocessing

    # Derive per-step decisions from mode
    decisions = _derive_decisions(
        mode=request.preprocessing_mode,
        assessment=assessment,
        explicit_decisions=request.preprocessing_decisions,
    )

    # Bridge the integer progress_callback API into on_stage_progress
    def _pct_adapter(step: int, total: int, message: str) -> None:
        pct = (step / total * 100.0) if total else 0.0
        progress.on_stage_progress(message, pct=pct)  # type: ignore[union-attr]

    try:
        processed, applied_steps = apply_preprocessing(
            audio,
            config,
            progress_callback=_pct_adapter,
            preprocessing_decisions=decisions,
        )
    except Exception as e:
        logger.error(f"Preprocessing failed: {e}")
        progress.on_stage_complete("preprocessing")
        return PreprocessResult(
            success=False,
            assessment=assessment,
            compliance=compliance,
            errors=[f"Preprocessing failed: {e}"],
            duration_seconds=time.time() - t0,
        )

    progress.on_log(
        f"Applied steps: {applied_steps or ['none']}",
        level="info",
    )
    progress.on_stage_complete("preprocessing")

    # No-op: no DSP steps applied — do not export a duplicate file
    if applied_steps == [] or applied_steps == ["skipped_already_compliant"]:
        progress.on_stage_start("exporting")
        progress.on_log(
            "No preprocessing steps were applied; skipping export to avoid duplicate file.",
            level="warning",
        )
        progress.on_stage_complete("exporting")
        progress.on_stage_start("finalizing")
        elapsed = time.time() - t0
        progress.on_log(f"Completed in {elapsed:.1f}s", level="info")
        progress.on_stage_complete("finalizing")
        return PreprocessResult(
            success=True,
            output_path=None,
            applied_steps=applied_steps,
            assessment=assessment,
            compliance=compliance,
            duration_seconds=elapsed,
            warnings=[
                "No steps applied; output file was not written. "
                "File is already compliant or no steps were selected."
            ],
        )

    # ------------------------------------------------------------------
    # Phase 4: Export
    # ------------------------------------------------------------------
    progress.on_stage_start("exporting")

    try:
        output_path = _resolve_output_path(
            input_path=request.input_path,
            output_dir=request.output_dir,
            output_format=request.output_format,
            overwrite=request.overwrite,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        processed.export(str(output_path), format=request.output_format)
        progress.on_log(f"Exported to: {output_path}", level="info")
    except Exception as e:
        logger.error(f"Export failed: {e}")
        progress.on_stage_complete("exporting")
        return PreprocessResult(
            success=False,
            assessment=assessment,
            compliance=compliance,
            applied_steps=applied_steps,
            errors=[f"Export failed: {e}"],
            duration_seconds=time.time() - t0,
        )

    progress.on_stage_complete("exporting")

    # ------------------------------------------------------------------
    # Phase 5: Finalize
    # ------------------------------------------------------------------
    progress.on_stage_start("finalizing")
    elapsed = time.time() - t0
    progress.on_log(f"Completed in {elapsed:.1f}s", level="info")
    progress.on_stage_complete("finalizing")

    return PreprocessResult(
        success=True,
        output_path=output_path,
        applied_steps=applied_steps,
        assessment=assessment,
        compliance=compliance,
        duration_seconds=elapsed,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _derive_decisions(
    mode: str,
    assessment: Optional[AudioAssessment],
    explicit_decisions: Optional[Dict[str, bool]],
) -> Optional[Dict[str, bool]]:
    """
    Translate preprocessing_mode into a decisions dict for apply_preprocessing.

    "auto"     — use suggested_steps from assessment (intelligent; empty if no assessment)
    "selected" — use explicit_decisions as-is
    "off"      — never reached here (caller returns early)
    """
    if mode == "auto":
        suggested = (assessment or {}).get("suggested_steps", [])
        return {step: True for step in suggested}
    if mode == "selected":
        return explicit_decisions or {}
    return {}


def _resolve_output_path(
    input_path: Path,
    output_dir: Optional[Path],
    output_format: str,
    overwrite: bool,
) -> Path:
    """
    Derive the output file path.

    Base name: {stem}_preprocessed.{ext}
    If overwrite=False and the base exists, auto-increment: _preprocessed_01, _02, …
    Raises RuntimeError after 99 attempts.
    """
    base_dir = output_dir or input_path.parent
    base = base_dir / f"{input_path.stem}_preprocessed.{output_format}"

    if overwrite or not base.exists():
        return base

    for i in range(1, 100):
        candidate = base_dir / f"{input_path.stem}_preprocessed_{i:02d}.{output_format}"
        if not candidate.exists():
            return candidate

    raise RuntimeError(
        f"Could not find a free output filename after 99 attempts "
        f"(base: {base}). Enable overwrite or clear existing files."
    )
