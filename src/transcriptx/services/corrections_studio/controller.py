"""
CorrectionsStudioController: thin DB-session-managing orchestrator.

Each method opens a DB session, instantiates CorrectionService, calls it,
commits/rolls back, and closes. No Streamlit imports. All return values are
plain dicts safe to store in st.session_state.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from transcriptx.core.utils.logger import get_logger
from transcriptx.database.database import get_session
from transcriptx.services.corrections_studio.service import CorrectionService

logger = get_logger()


class CorrectionsStudioController:
    """Orchestrator for Corrections Studio. Methods map 1:1 to UI actions."""

    def start_or_resume(self, transcript_path: str) -> Dict[str, Any]:
        session = get_session()
        try:
            svc = CorrectionService(session)
            result = svc.start_or_resume_session(transcript_path)
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        session = get_session()
        try:
            svc = CorrectionService(session)
            return svc.get_session(session_id)
        finally:
            session.close()

    def generate_candidates(
        self, session_id: str, force: bool = False
    ) -> List[Dict[str, Any]]:
        session = get_session()
        try:
            svc = CorrectionService(session)
            result = svc.generate_candidates(session_id, force=force)
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def list_candidates(
        self,
        session_id: str,
        status_filter: Optional[str] = None,
        kind_filter: Optional[List[str]] = None,
        confidence_min: Optional[float] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        session = get_session()
        try:
            svc = CorrectionService(session)
            return svc.list_candidates(
                session_id,
                status_filter=status_filter,
                kind_filter=kind_filter,
                confidence_min=confidence_min,
                offset=offset,
                limit=limit,
            )
        finally:
            session.close()

    def count_candidates(
        self,
        session_id: str,
        status_filter: Optional[str] = None,
        kind_filter: Optional[List[str]] = None,
        confidence_min: Optional[float] = None,
    ) -> int:
        session = get_session()
        try:
            svc = CorrectionService(session)
            return svc.count_candidates(
                session_id,
                status_filter=status_filter,
                kind_filter=kind_filter,
                confidence_min=confidence_min,
            )
        finally:
            session.close()

    def record_decision(
        self,
        session_id: str,
        candidate_id: str,
        decision: str,
        selected_occurrence_keys: Optional[List[str]] = None,
        learn_rule_params: Optional[Dict[str, Any]] = None,
    ) -> None:
        session = get_session()
        try:
            svc = CorrectionService(session)
            svc.record_decision(
                session_id,
                candidate_id,
                decision,
                selected_occurrence_keys=selected_occurrence_keys,
                learn_rule_params=learn_rule_params,
            )
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def compute_preview(self, session_id: str) -> Dict[str, Any]:
        session = get_session()
        try:
            svc = CorrectionService(session)
            return svc.compute_preview(session_id)
        finally:
            session.close()

    def apply_and_export(
        self, session_id: str, export_path: Optional[str] = None
    ) -> Dict[str, Any]:
        session = get_session()
        try:
            svc = CorrectionService(session)
            result = svc.apply_and_export(session_id, export_path=export_path)
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_session_stats(self, session_id: str) -> Dict[str, int]:
        session = get_session()
        try:
            svc = CorrectionService(session)
            return svc.repo.get_session_stats(session_id)
        finally:
            session.close()

    def get_candidate_local_diff(
        self, session_id: str, candidate_id: str
    ) -> Dict[str, Any]:
        session = get_session()
        try:
            svc = CorrectionService(session)
            return svc.get_candidate_local_diff(session_id, candidate_id)
        finally:
            session.close()

    def list_transcripts(self) -> List[Dict[str, Any]]:
        """List transcripts using the same discovery as Library/Speaker Studio (config + recursive scan)."""
        try:
            from transcriptx.app.compat import discover_all_transcript_paths
            from transcriptx.services.speaker_studio.controller import (
                SpeakerStudioController,
            )

            paths = discover_all_transcript_paths(None)
            if not paths:
                # Fallback: SegmentIndex only looks in DATA_DIR/transcripts (flat)
                ctrl = SpeakerStudioController()
                transcripts = ctrl.list_transcripts(canonical_only=False)
            else:
                ctrl = SpeakerStudioController()
                transcripts = ctrl.list_transcripts_from_paths(paths)
            return [
                {
                    "path": t.path,
                    "base_name": t.base_name,
                    "segment_count": t.segment_count,
                    "speaker_map_status": t.speaker_map_status,
                }
                for t in transcripts
            ]
        except Exception as exc:
            logger.warning("Could not list transcripts: %s", exc)
            return []
