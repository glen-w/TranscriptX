"""Public import contract for Corrections Studio candidate generation facade."""

from __future__ import annotations

from transcriptx.services.corrections_studio.candidate_service import (
    CorrectionsStudioCandidateService,
    GenerateCandidatesResult,
)
from transcriptx.services.corrections_studio.service import CorrectionService


def test_candidate_service_public_symbols() -> None:
    assert callable(CorrectionsStudioCandidateService)
    assert hasattr(CorrectionsStudioCandidateService, "generate_candidates")
    assert GenerateCandidatesResult is not None


def test_correction_service_delegates_generate_candidates() -> None:
    assert hasattr(CorrectionService, "generate_candidates")
    assert callable(CorrectionService.generate_candidates)
