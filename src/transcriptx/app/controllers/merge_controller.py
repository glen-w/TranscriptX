"""
Merge controller — thin boundary between the web layer and the merge workflow.
No prompts, no prints, no formatting concerns.
"""

from __future__ import annotations

from transcriptx.app.models.errors import WorkflowExecutionError
from transcriptx.app.models.requests import MergeRequest
from transcriptx.app.models.results import MergeResult
from transcriptx.app.progress import ProgressCallback
from transcriptx.app.workflows.merge import run_merge


class MergeController:
    """
    Delegates a MergeRequest to run_merge.

    Responsibilities: exception boundary only.  All workflow logic
    lives in app.workflows.merge.
    """

    def run_merge(
        self,
        request: MergeRequest,
        progress: ProgressCallback | None = None,
    ) -> MergeResult:
        """
        Delegate a MergeRequest to the workflow.

        Raises WorkflowExecutionError on unexpected exceptions.
        Expected failures (validation, missing files, merge error) are
        returned as MergeResult(success=False, errors=[...]).
        """
        try:
            return run_merge(request, progress)
        except Exception as e:
            raise WorkflowExecutionError(str(e)) from e
