"""
Analysis controller. Thin coordination - validates, calls workflow, normalizes result.
"""

from __future__ import annotations

from typing import Any, MutableMapping, Optional

from transcriptx.app.models.requests import AnalysisRequest
from transcriptx.app.models.results import AnalysisResult
from transcriptx.app.progress import ProgressCallback
from transcriptx.app.workflows.analysis import run_analysis, validate_analysis_readiness
from transcriptx.app.module_resolution import resolve_modules
from transcriptx.core import get_available_modules, get_default_modules
from transcriptx.app.models.errors import ValidationError, WorkflowExecutionError


class AnalysisController:
    """Orchestrates analysis workflow. No prompts, no prints."""

    def validate_readiness(self, request: AnalysisRequest) -> list[str]:
        """Pre-run validation. Returns list of error messages; empty if ready."""
        return validate_analysis_readiness(request)

    def run_analysis(
        self,
        request: AnalysisRequest,
        progress: ProgressCallback | None = None,
        snapshot: Optional[MutableMapping[str, Any]] = None,
    ) -> AnalysisResult:
        """Run single-transcript analysis."""
        try:
            return run_analysis(request, progress, snapshot=snapshot)
        except (FileNotFoundError, ValueError) as e:
            raise ValidationError(str(e)) from e
        except Exception as e:
            raise WorkflowExecutionError(str(e)) from e

    def get_available_modules(self) -> list[str]:
        """Return list of available module IDs."""
        return get_available_modules()

    def get_default_modules(self, transcript_paths: list[str]) -> list[str]:
        """Return default module list for given transcript(s)."""
        return get_default_modules(transcript_paths)

    def resolve_modules(
        self,
        transcript_paths: list[str],
        mode: str = "quick",
        profile: str | None = None,
        custom_ids: list[str] | None = None,
    ) -> list[str]:
        """Resolve effective module list. Single source of truth."""
        return resolve_modules(
            transcript_paths,
            mode=mode,
            profile=profile,
            custom_ids=custom_ids,
        )
