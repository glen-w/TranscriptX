"""
Prompt-free batch analysis workflow. No questionary, rich, click, or typer.

Accepts BatchAnalysisRequest, runs analysis on each transcript, returns BatchAnalysisResult.
"""

from __future__ import annotations

from pathlib import Path

from transcriptx.app.compat import discover_all_transcript_paths
from transcriptx.app.models.requests import AnalysisRequest, BatchAnalysisRequest
from transcriptx.app.models.results import AnalysisResult, BatchAnalysisResult
from transcriptx.app.progress import NullProgress, ProgressCallback
from transcriptx.app.workflows.analysis import run_analysis


def run_batch_analysis(
    request: BatchAnalysisRequest,
    progress: ProgressCallback | None = None,
) -> BatchAnalysisResult:
    """
    Run analysis on selected transcripts or all in folder. No prompts, no prints.
    """
    if progress is None:
        progress = NullProgress()

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
        transcript_paths = discover_all_transcript_paths(folder)

    if not transcript_paths:
        return BatchAnalysisResult(
            success=True,
            transcript_count=0,
            message="No transcript JSON files found",
        )

    errors: list[str] = []
    success_count = 0
    total = len(transcript_paths)

    for idx, path in enumerate(transcript_paths):
        progress.on_stage_start("batch_analysis")
        progress.on_stage_progress(
            f"Processing {idx + 1}/{total}: {path.name}", pct=(idx + 1) / total
        )
        progress.on_log(f"Analyzing {path.name}", level="info")

        analysis_request = AnalysisRequest(
            transcript_path=path,
            mode=request.analysis_mode,
            modules=request.selected_modules,
            skip_speaker_mapping=request.skip_speaker_gate,
            persist=request.persist,
        )
        result: AnalysisResult = run_analysis(analysis_request, progress)
        if result.success:
            success_count += 1
        else:
            errors.extend([f"{path.name}: {e}" for e in result.errors])

        progress.on_stage_complete("batch_analysis")

    return BatchAnalysisResult(
        success=success_count > 0 and len(errors) == 0,
        transcript_count=total,
        errors=errors if errors else [],
        message=f"Processed {total} transcript(s), {success_count} succeeded",
    )
