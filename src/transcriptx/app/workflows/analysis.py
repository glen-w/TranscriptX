"""
Prompt-free analysis workflow. No questionary, rich, click, or typer.

Accepts explicit AnalysisRequest, returns structured AnalysisResult.
Uses ProgressCallback for status updates. Caller is responsible for
output capture if wrapping legacy code that still prints.
"""

from __future__ import annotations

import time
from pathlib import Path

from transcriptx.app.models.requests import AnalysisRequest
from transcriptx.app.models.results import AnalysisResult
from transcriptx.app.progress import NullProgress, ProgressCallback
from transcriptx.core import (
    get_available_modules,
    get_default_modules,
    run_analysis_pipeline,
)
from transcriptx.core.analysis.selection import (
    apply_analysis_mode_settings,
    filter_modules_by_mode,
)
from transcriptx.core.pipeline.run_schema import RunManifestInput
from transcriptx.core.utils.config import get_config


def validate_analysis_readiness(request: AnalysisRequest) -> list[str]:
    """
    Pre-run validation. Returns list of error messages; empty if ready.
    """
    errors: list[str] = []
    path = Path(request.transcript_path)
    if not path.exists():
        errors.append(f"Transcript file not found: {path}")
        return errors
    if path.suffix.lower() != ".json":
        errors.append(f"Expected JSON transcript, got: {path.suffix}")
    if request.mode not in ("quick", "full"):
        errors.append(f"Invalid mode: {request.mode}. Must be 'quick' or 'full'")
    valid_profiles = (
        "balanced",
        "academic",
        "business",
        "casual",
        "technical",
        "interview",
    )
    if request.profile and request.profile not in valid_profiles:
        errors.append(f"Invalid profile: {request.profile}")
    if request.modules is not None:
        available = get_available_modules()
        invalid = [m for m in request.modules if m not in available]
        if invalid:
            errors.append(f"Invalid modules: {', '.join(invalid)}")
    return errors


def run_analysis(
    request: AnalysisRequest,
    progress: ProgressCallback | None = None,
) -> AnalysisResult:
    """
    Run single-transcript analysis. No prompts, no prints.
    """
    if progress is None:
        progress = NullProgress()

    path = Path(request.transcript_path)
    if not path.exists():
        return AnalysisResult(
            success=False,
            run_dir=Path(),
            manifest_path=Path(),
            modules_executed=[],
            warnings=[],
            errors=[f"Transcript file not found: {path}"],
            status="failed",
        )

    progress.on_stage_start("validating")
    errors = validate_analysis_readiness(request)
    if errors:
        progress.on_stage_complete("validating")
        return AnalysisResult(
            success=False,
            run_dir=Path(),
            manifest_path=Path(),
            modules_executed=[],
            warnings=[],
            errors=errors,
            status="failed",
        )
    progress.on_stage_complete("validating")

    available = get_available_modules()
    default = get_default_modules([str(path)])
    if request.modules is None or (
        isinstance(request.modules, list) and len(request.modules) == 0
    ):
        selected = default
    elif (
        isinstance(request.modules, list)
        and len(request.modules) == 1
        and request.modules[0].lower() == "all"
    ):
        selected = default
    elif request.modules:
        invalid = [m for m in request.modules if m not in available]
        if invalid:
            return AnalysisResult(
                success=False,
                run_dir=Path(),
                manifest_path=Path(),
                modules_executed=[],
                warnings=[],
                errors=[f"Invalid modules: {', '.join(invalid)}"],
                status="failed",
            )
        selected = list(request.modules)
    else:
        selected = default

    apply_analysis_mode_settings(request.mode, request.profile)
    filtered = filter_modules_by_mode(selected, request.mode)

    output_dir_str: str | None = None
    if request.output_dir:
        output_dir_str = str(Path(request.output_dir))
        config = get_config()
        config.output.base_output_dir = output_dir_str

    progress.on_stage_start("running_pipeline")
    progress.on_log(f"Running modules: {', '.join(filtered)}", level="info")

    start = time.perf_counter()
    try:
        manifest = RunManifestInput.from_cli_kwargs(
            transcript_file=path,
            mode=request.mode,
            modules=filtered,
            profile=request.profile,
            skip_confirm=True,
            output_dir=output_dir_str,
            include_unidentified_speakers=request.include_unidentified_speakers,
            skip_speaker_gate=request.skip_speaker_mapping,
            persist=request.persist,
        )
        results = run_analysis_pipeline(manifest=manifest)
    except Exception as e:
        duration = time.perf_counter() - start
        progress.on_stage_complete("running_pipeline")
        return AnalysisResult(
            success=False,
            run_dir=Path(),
            manifest_path=Path(),
            modules_executed=[],
            warnings=[],
            errors=[str(e)],
            duration_seconds=duration,
            status="failed",
        )

    duration = time.perf_counter() - start
    progress.on_stage_complete("running_pipeline")

    output_dir = results.get("output_dir", "")
    output_path = Path(output_dir) if output_dir else Path()
    manifest_path = output_path / "manifest.json" if output_path else Path()
    modules_run = results.get("modules_run", [])
    result_errors = results.get("errors", [])

    status = "completed"
    if result_errors:
        status = "partial" if modules_run else "failed"

    return AnalysisResult(
        success=len(result_errors) == 0 or len(modules_run) > 0,
        run_dir=output_path,
        manifest_path=manifest_path if manifest_path.exists() else Path(),
        modules_executed=modules_run,
        warnings=[],
        errors=result_errors,
        duration_seconds=duration,
        status=status,
    )
