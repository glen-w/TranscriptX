"""
Batch controller. Batch analysis. No prompts, no prints.
"""

from __future__ import annotations

from pathlib import Path

from transcriptx.app.models.requests import BatchAnalysisRequest
from transcriptx.app.models.results import BatchAnalysisResult
from transcriptx.app.progress import ProgressCallback
from transcriptx.app.workflows.batch import run_batch_analysis
from transcriptx.app.models.errors import ValidationError, WorkflowExecutionError


class BatchController:
    """Orchestrates batch analysis. No prompts, no prints."""

    def run_batch_analysis(
        self,
        request: BatchAnalysisRequest,
        progress: ProgressCallback | None = None,
    ) -> BatchAnalysisResult:
        """Run analysis on selected transcripts or all in folder."""
        try:
            if request.transcript_paths:
                paths = [Path(p) for p in request.transcript_paths]
                if not paths:
                    raise ValidationError("transcript_paths must not be empty")
                for p in paths:
                    if not p.exists():
                        raise ValidationError(f"Transcript not found: {p}")
            else:
                folder = Path(request.folder) if request.folder else None
                if not folder:
                    raise ValidationError("Provide either transcript_paths or folder")
                if not folder.exists():
                    raise ValidationError(f"Folder not found: {folder}")
                if not folder.is_dir():
                    raise ValidationError(f"Not a directory: {folder}")
            return run_batch_analysis(request, progress)
        except ValidationError:
            raise
        except Exception as e:
            raise WorkflowExecutionError(str(e)) from e
