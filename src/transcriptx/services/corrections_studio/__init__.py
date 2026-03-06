"""
Corrections Studio services: DB-backed, resumable correction review workflow.

Used by the Corrections Studio Streamlit page. All business logic is in
CorrectionService; the controller is a thin DB-session-managing orchestrator.
"""

from transcriptx.services.corrections_studio.service import CorrectionService
from transcriptx.services.corrections_studio.controller import (
    CorrectionsStudioController,
)

__all__ = [
    "CorrectionService",
    "CorrectionsStudioController",
]
