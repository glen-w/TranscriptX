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
        """Run analysis on all transcripts in folder."""
        try:
            folder = Path(request.folder)
            if not folder.exists():
                raise ValidationError(f"Folder not found: {folder}")
            if not folder.is_dir():
                raise ValidationError(f"Not a directory: {folder}")
            return run_batch_analysis(request, progress)
        except ValidationError:
            raise
        except Exception as e:
            raise WorkflowExecutionError(str(e)) from e
