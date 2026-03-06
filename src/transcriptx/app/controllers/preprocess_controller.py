"""
Preprocess controller. Audio convert/merge/compress/preprocess. No prompts, no prints.
"""

from __future__ import annotations

from transcriptx.app.models.requests import PreprocessRequest
from transcriptx.app.models.results import PreprocessResult
from transcriptx.app.progress import ProgressCallback
from transcriptx.app.workflows.preprocess import run_preprocess
from transcriptx.app.models.errors import WorkflowExecutionError


class PreprocessController:
    """Orchestrates audio preprocessing. No prompts, no prints."""

    def run_preprocess(
        self,
        request: PreprocessRequest,
        progress: ProgressCallback | None = None,
    ) -> PreprocessResult:
        """Run audio preprocessing (convert, merge, compress, preprocess)."""
        try:
            return run_preprocess(request, progress)
        except Exception as e:
            raise WorkflowExecutionError(str(e)) from e
