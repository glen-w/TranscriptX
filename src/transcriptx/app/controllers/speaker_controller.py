"""
Speaker controller. Identify speakers. No prompts, no prints.
"""

from __future__ import annotations


from transcriptx.app.models.requests import SpeakerIdentificationRequest
from transcriptx.app.models.results import SpeakerIdentificationResult
from transcriptx.app.progress import ProgressCallback
from transcriptx.app.workflows.speaker import identify_speakers
from transcriptx.app.models.errors import ValidationError, WorkflowExecutionError


class SpeakerController:
    """Orchestrates speaker identification. No prompts, no prints."""

    def identify_speakers(
        self,
        request: SpeakerIdentificationRequest,
        progress: ProgressCallback | None = None,
    ) -> SpeakerIdentificationResult:
        """Run speaker identification on transcript(s)."""
        try:
            return identify_speakers(request, progress)
        except (FileNotFoundError, ValueError) as e:
            raise ValidationError(str(e)) from e
        except Exception as e:
            raise WorkflowExecutionError(str(e)) from e
