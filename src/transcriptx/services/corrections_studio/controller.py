"""Corrections studio controller."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from transcriptx.services.corrections_studio.manual_propose_service import (
    ManualProposeResult,
)
from transcriptx.services.corrections_studio.schema import (
    CandidateLocalDiffResult,
    StudioCandidate,
    StudioExportResult,
    StudioPreviewResult,
    StudioReviewStats,
    StudioSessionDocument,
    StudioTranscriptSummary,
)
from transcriptx.services.corrections_studio.service import CorrectionService


class CorrectionsStudioController:
    """Orchestrator for Corrections Studio. Methods map 1:1 to UI actions."""

    def __init__(self) -> None:
        self._svc = CorrectionService()

    def start_or_resume(self, transcript_path: str) -> StudioSessionDocument:
        return self._svc.start_or_resume_session(transcript_path)

    def load_session(self, session_id: str) -> Optional[StudioSessionDocument]:
        return self._svc.load_session(session_id)

    def generate_candidates(self, session_id: str, force: bool = False):
        return self._svc.generate_candidates(session_id, force=force)

    def list_candidates(
        self,
        session_id: str,
        status_filter: Optional[str] = None,
        kind_filter: Optional[List[str]] = None,
        confidence_min: Optional[float] = None,
        source_filter: Optional[List[str]] = None,
        offset: int = 0,
        limit: int = 100,
        *,
        generation_id: Optional[int] = None,
        include_historical: bool = False,
    ) -> List[StudioCandidate]:
        return self._svc.list_candidates(
            session_id,
            status_filter=status_filter,
            kind_filter=kind_filter,
            confidence_min=confidence_min,
            source_filter=source_filter,
            offset=offset,
            limit=limit,
            generation_id=generation_id,
            include_historical=include_historical,
        )

    def count_candidates(
        self,
        session_id: str,
        status_filter: Optional[str] = None,
        kind_filter: Optional[List[str]] = None,
        confidence_min: Optional[float] = None,
        source_filter: Optional[List[str]] = None,
        *,
        generation_id: Optional[int] = None,
        include_historical: bool = False,
    ) -> int:
        return self._svc.count_candidates(
            session_id,
            status_filter=status_filter,
            kind_filter=kind_filter,
            confidence_min=confidence_min,
            source_filter=source_filter,
            generation_id=generation_id,
            include_historical=include_historical,
        )

    def get_generation_diagnostics(self, session_id: str) -> Optional[dict]:
        return self._svc.get_generation_diagnostics(session_id)

    def record_decision(
        self,
        session_id: str,
        candidate_id: str,
        decision: str,
        selected_occurrence_keys: Optional[List[str]] = None,
        learn_rule_params: Optional[Dict[str, Any]] = None,
        review_target_raw: Optional[str] = None,
    ) -> None:
        self._svc.record_decision(
            session_id,
            candidate_id,
            decision,
            selected_occurrence_keys=selected_occurrence_keys,
            learn_rule_params=learn_rule_params,
            review_target_raw=review_target_raw,
        )

    def compute_preview(self, session_id: str) -> StudioPreviewResult:
        return self._svc.compute_preview(session_id)

    def apply_and_export(
        self, session_id: str, export_path: Optional[str] = None
    ) -> StudioExportResult:
        return self._svc.apply_and_export(session_id, export_path=export_path)

    def apply_and_export_scoped(
        self,
        session_id: str,
        candidate_ids: List[str],
        occurrence_keys: Optional[List[str]] = None,
        export_path: Optional[str] = None,
    ) -> StudioExportResult:
        return self._svc.apply_and_export_scoped(
            session_id,
            candidate_ids=candidate_ids,
            occurrence_keys=occurrence_keys,
            export_path=export_path,
        )

    def propose_manual_correction(
        self,
        session_id: str,
        *,
        segment_id: Optional[str] = None,
        segment_index: Optional[int] = None,
        span: Tuple[int, int],
        wrong_text: str,
        right_text: str,
        auto_accept: bool = False,
        supersede_existing: bool = False,
    ) -> ManualProposeResult:
        return self._svc.propose_manual_correction(
            session_id,
            segment_id=segment_id,
            segment_index=segment_index,
            span=span,
            wrong_text=wrong_text,
            right_text=right_text,
            auto_accept=auto_accept,
            supersede_existing=supersede_existing,
        )

    def get_session_stats(self, session_id: str) -> StudioReviewStats:
        return self._svc.get_session_stats(session_id)

    def get_candidate_local_diff(
        self,
        session_id: str,
        candidate_id: str,
        transient_target_raw: Optional[str] = None,
    ) -> CandidateLocalDiffResult:
        return self._svc.get_candidate_local_diff(
            session_id, candidate_id, transient_target_raw=transient_target_raw
        )

    def list_transcript_summaries_for_studio(self) -> List[StudioTranscriptSummary]:
        """List managed transcripts for the Corrections Studio picker (no SpeakerStudioController)."""
        return self._svc.list_transcript_summaries_for_studio()

    def list_transcripts(self) -> List[StudioTranscriptSummary]:
        """Deprecated alias; prefer list_transcript_summaries_for_studio."""
        return self.list_transcript_summaries_for_studio()
