"""
Transcription controller — thin boundary between the web layer and transcription workflow.
"""

from __future__ import annotations

from transcriptx.app.models.errors import WorkflowExecutionError
from transcriptx.app.models.requests import TranscriptionRequest
from transcriptx.app.models.results import TranscriptionBatchResult
from transcriptx.app.progress import ProgressCallback
from transcriptx.app.workflows.transcription import run_transcription_workflow


class TranscriptionController:
    """Delegates TranscriptionRequest to run_transcription_workflow."""

    def run_transcription(
        self,
        request: TranscriptionRequest,
        progress: ProgressCallback | None = None,
    ) -> TranscriptionBatchResult:
        try:
            return run_transcription_workflow(request, progress)
        except Exception as e:
            raise WorkflowExecutionError(str(e)) from e
