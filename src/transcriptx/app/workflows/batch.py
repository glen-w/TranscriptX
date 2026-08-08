"""
Prompt-free batch analysis workflow. No questionary, rich, click, or typer.

Accepts BatchAnalysisRequest, runs analysis on each transcript, returns BatchAnalysisResult.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from transcriptx.core.utils.file_discovery import discover_managed_transcript_paths
from transcriptx.app.models.requests import AnalysisRequest, BatchAnalysisRequest
from transcriptx.app.models.results import (
    AnalysisResult,
    BatchAnalysisResult,
    RunSummary,
)
from transcriptx.app.progress import NullProgress, ProgressCallback
from transcriptx.app.workflows.analysis import (
    _coerce_llm_model_selection,
    run_analysis,
)


def _run_summary_from_analysis(path: Path, result: AnalysisResult) -> RunSummary:
    run_dir = Path(result.run_dir)
    try:
        created_at = datetime.fromtimestamp(run_dir.stat().st_mtime)
    except OSError:
        created_at = datetime.now()
    return RunSummary(
        run_dir=run_dir,
        transcript_path=Path(path),
        run_id=run_dir.name,
        created_at=created_at,
        selected_modules=list(result.modules_executed or []),
        manifest_path=Path(result.manifest_path) if result.manifest_path else Path(),
        status=result.status or "completed",
        duration_seconds=result.duration_seconds,
        warnings_count=len(result.warnings) if result.warnings else None,
    )


def run_batch_analysis(
    request: BatchAnalysisRequest,
    progress: ProgressCallback | None = None,
) -> BatchAnalysisResult:
    """
    Run analysis on selected transcripts or all in folder. No prompts, no prints.
    """
    if progress is None:
        progress = NullProgress()

    try:
        _coerce_llm_model_selection(request.llm_model_selection)
    except ValueError as exc:
        return BatchAnalysisResult(
            success=False,
            transcript_count=0,
            errors=[f"Invalid llm_model_selection: {exc}"],
        )

    if request.transcript_paths:
        transcript_paths = [Path(p) for p in request.transcript_paths]
    else:
        folder = Path(request.folder) if request.folder else None
        if not folder or not folder.exists() or not folder.is_dir():
            return BatchAnalysisResult(
                success=False,
                transcript_count=0,
                errors=[f"Folder not found or not a directory: {folder}"],
            )
        transcript_paths = discover_managed_transcript_paths(folder)

    if not transcript_paths:
        return BatchAnalysisResult(
            success=True,
            transcript_count=0,
            message="No transcript JSON files found",
        )

    errors: list[str] = []
    runs: list[RunSummary] = []
    success_count = 0
    total = len(transcript_paths)

    for idx, path in enumerate(transcript_paths):
        progress.on_stage_start("batch_analysis")
        # Leave pct to nested per-transcript module events (0–100). Passing a
        # 0–1 batch fraction here used to collapse the live bar.
        # current_item persists on the snapshot while module events overwrite
        # latest_event — so the UI can keep showing which transcript is running.
        item_label = f"{idx + 1}/{total} · {path.stem}"
        progress.on_stage_progress(
            f"Processing {idx + 1}/{total}: {path.name}",
            pct=None,
            current_item=item_label,
        )
        progress.on_log(f"Analyzing {path.name}", level="info")

        analysis_request = AnalysisRequest(
            transcript_path=path,
            mode=request.analysis_mode,
            modules=request.selected_modules,
            analysis_preset=request.analysis_preset,
            persist=request.persist,
            llm_model_selection=request.llm_model_selection,
            llm_custom_qa_questions=request.llm_custom_qa_questions,
        )
        result: AnalysisResult = run_analysis(analysis_request, progress)
        if result.success:
            success_count += 1
            runs.append(_run_summary_from_analysis(path, result))
        else:
            errors.extend([f"{path.name}: {e}" for e in result.errors])

        progress.on_stage_complete("batch_analysis")

    return BatchAnalysisResult(
        success=success_count > 0 and len(errors) == 0,
        transcript_count=total,
        errors=errors if errors else [],
        message=f"Processed {total} transcript(s), {success_count} succeeded",
        runs=runs,
    )
