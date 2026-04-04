"""
Corrections Studio services: DB-backed, resumable correction review workflow.

Used by the Corrections Studio Streamlit page. All business logic is in
CorrectionService; the controller is a thin DB-session-managing orchestrator.
"""

from transcriptx.services.corrections_studio.compile import (
    CompiledStudioApply,
    compile_studio_to_engine_apply,
)
from transcriptx.services.corrections_studio.controller import (
    CorrectionsStudioController,
)
from transcriptx.services.corrections_studio.reconcile import (
    reconcile_snapshot_from_events,
)
from transcriptx.services.corrections_studio.service import CorrectionService
from transcriptx.services.corrections_studio.session_service import (
    CorrectionsStudioSessionService,
)

__all__ = [
    "CompiledStudioApply",
    "CorrectionService",
    "CorrectionsStudioController",
    "CorrectionsStudioSessionService",
    "compile_studio_to_engine_apply",
    "reconcile_snapshot_from_events",
]
