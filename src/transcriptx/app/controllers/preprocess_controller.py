"""
Preprocess controller — thin boundary between the web layer and the preprocessing workflow.
No prompts, no prints, no formatting concerns.
"""

from __future__ import annotations

from transcriptx.app.models.requests import PreprocessRequest
from transcriptx.app.models.results import PreprocessResult
from transcriptx.app.progress import ProgressCallback
from transcriptx.app.workflows.preprocess import run_preprocess
from transcriptx.app.models.errors import WorkflowExecutionError


class PreprocessController:
    """
    Validates and delegates to run_preprocess.

    Responsibilities: exception boundary only.  All workflow logic
    lives in app.workflows.preprocess.
    """

    def run_preprocess(
        self,
        request: PreprocessRequest,
        progress: ProgressCallback | None = None,
    ) -> PreprocessResult:
        """
        Delegate a PreprocessRequest to the workflow.

        Raises WorkflowExecutionError on unexpected exceptions.
        Expected failures (bad input, missing file, invalid mode combination)
        are returned as PreprocessResult(success=False, errors=[...]).
        """
        try:
            return run_preprocess(request, progress)
        except Exception as e:
            raise WorkflowExecutionError(str(e)) from e
