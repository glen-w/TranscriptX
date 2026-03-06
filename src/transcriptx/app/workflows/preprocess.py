"""
Prompt-free audio preprocessing workflow. No questionary, rich, click, or typer.

Placeholder: full extraction from wav_processing_workflow deferred.
"""

from __future__ import annotations

from transcriptx.app.models.requests import PreprocessRequest
from transcriptx.app.models.results import PreprocessResult
from transcriptx.app.progress import NullProgress, ProgressCallback


def run_preprocess(
    request: PreprocessRequest,
    progress: ProgressCallback | None = None,
) -> PreprocessResult:
    """
    Run audio preprocessing (convert, merge, compress, preprocess).
    Currently a stub - use CLI transcriptx prep-audio / process-wav.
    """
    if progress is None:
        progress = NullProgress()
    progress.on_stage_start("preprocess")
    progress.on_log(
        "Audio prep GUI not yet implemented. Use: transcriptx prep-audio", level="info"
    )
    progress.on_stage_complete("preprocess")
    return PreprocessResult(
        success=False,
        output_path=None,
        errors=[
            "Audio prep operations require CLI: transcriptx prep-audio, transcriptx process-wav"
        ],
    )
