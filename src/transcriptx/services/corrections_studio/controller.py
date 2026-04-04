"""Corrections studio controller."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from transcriptx.core.utils.logger import get_logger
from transcriptx.services.corrections_studio.service import CorrectionService

logger = get_logger()


class CorrectionsStudioController:
    """Orchestrator for Corrections Studio. Methods map 1:1 to UI actions."""

    def __init__(self) -> None:
        self._svc = CorrectionService()

    def start_or_resume(self, transcript_path: str) -> Dict[str, Any]:
        return self._svc.start_or_resume_session(transcript_path)

    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self._svc.load_session(session_id)

    def generate_candidates(
        self, session_id: str, force: bool = False
    ) -> List[Dict[str, Any]]:
        return self._svc.generate_candidates(session_id, force=force)

    def list_candidates(
        self,
        session_id: str,
        status_filter: Optional[str] = None,
        kind_filter: Optional[List[str]] = None,
        confidence_min: Optional[float] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        return self._svc.list_candidates(
            session_id,
            status_filter=status_filter,
            kind_filter=kind_filter,
            confidence_min=confidence_min,
            offset=offset,
            limit=limit,
        )

    def count_candidates(
        self,
        session_id: str,
        status_filter: Optional[str] = None,
        kind_filter: Optional[List[str]] = None,
        confidence_min: Optional[float] = None,
    ) -> int:
        return self._svc.count_candidates(
            session_id,
            status_filter=status_filter,
            kind_filter=kind_filter,
            confidence_min=confidence_min,
        )

    def record_decision(
        self,
        session_id: str,
        candidate_id: str,
        decision: str,
        selected_occurrence_keys: Optional[List[str]] = None,
        learn_rule_params: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._svc.record_decision(
            session_id,
            candidate_id,
            decision,
            selected_occurrence_keys=selected_occurrence_keys,
            learn_rule_params=learn_rule_params,
        )

    def compute_preview(self, session_id: str) -> Dict[str, Any]:
        return self._svc.compute_preview(session_id)

    def apply_and_export(
        self, session_id: str, export_path: Optional[str] = None
    ) -> Dict[str, Any]:
        return self._svc.apply_and_export(session_id, export_path=export_path)

    def get_session_stats(self, session_id: str) -> Dict[str, int]:
        return self._svc.get_session_stats(session_id)

    def get_candidate_local_diff(
        self, session_id: str, candidate_id: str
    ) -> Dict[str, Any]:
        return self._svc.get_candidate_local_diff(session_id, candidate_id)

    def list_transcript_summaries_for_studio(self) -> List[Dict[str, Any]]:
        """List managed transcripts for the Corrections Studio picker (no SpeakerStudioController)."""
        try:
            from pathlib import Path

            from transcriptx.core.utils.file_discovery import (
                discover_managed_transcript_paths,
            )
            from transcriptx.services.speaker_studio.segment_index import (
                SegmentIndexService,
            )

            paths = discover_managed_transcript_paths(None)
            idx = SegmentIndexService()
            summaries: List[Dict[str, Any]] = []
            seen: set[str] = set()
            for p in paths:
                s = idx.summary_for_path(p)
                if s is None:
                    continue
                key = str(Path(s.path).resolve())
                if key in seen:
                    continue
                seen.add(key)
                summaries.append(
                    {
                        "path": s.path,
                        "base_name": s.base_name,
                        "segment_count": s.segment_count,
                        "speaker_map_status": s.speaker_map_status,
                    }
                )
            if not summaries:
                for t in idx.list_transcripts(canonical_only=False):
                    key = str(Path(t.path).resolve())
                    if key in seen:
                        continue
                    seen.add(key)
                    summaries.append(
                        {
                            "path": t.path,
                            "base_name": t.base_name,
                            "segment_count": t.segment_count,
                            "speaker_map_status": t.speaker_map_status,
                        }
                    )
            return sorted(summaries, key=lambda x: x["path"])
        except Exception as exc:
            logger.warning("Could not list transcripts: %s", exc)
            return []

    def list_transcripts(self) -> List[Dict[str, Any]]:
        """Deprecated alias; prefer list_transcript_summaries_for_studio."""
        return self.list_transcript_summaries_for_studio()
