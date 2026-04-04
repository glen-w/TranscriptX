"""
CorrectionService: façade over CorrectionsStudio* services (pass-through).

Business logic lives in session / candidate / review / preview / export services.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from transcriptx.core.store.corrections_session_store import CorrectionsSessionStore
from transcriptx.core.utils.canonicalization import compute_transcript_identity_hash
from transcriptx.io import load_segments
from transcriptx.services.corrections_studio.candidate_service import (
    STUDIO_DETECTOR_VERSION,
    CorrectionsStudioCandidateService,
)
from transcriptx.services.corrections_studio.export_service import (
    CorrectionsStudioExportService,
)
from transcriptx.services.corrections_studio.normalize import (
    normalize_cutover_session_blob,
)
from transcriptx.services.corrections_studio.preview_service import (
    CorrectionsStudioPreviewService,
)
from transcriptx.services.corrections_studio.review_service import (
    CorrectionsStudioReviewService,
)
from transcriptx.services.corrections_studio.schema import (
    SessionStartedPayload,
    StudioEventEnvelope,
    StudioSessionDocument,
)
from transcriptx.services.corrections_studio.session_service import (
    CorrectionsStudioSessionService,
)
from transcriptx.services.corrections_studio import studio_metrics


def normalize_transcript_path(path: str) -> str:
    return str(Path(path).expanduser().resolve())


_STORE = CorrectionsSessionStore()


def _document_to_api_dict(doc: StudioSessionDocument) -> Dict[str, Any]:
    d = doc.model_dump(mode="json")
    d["candidates_stale"] = _detector_stale(doc)
    return d


def _detector_stale(doc: StudioSessionDocument) -> bool:
    if not doc.current_generation:
        return False
    return (
        doc.current_generation.generation_manifest.detector_version
        != STUDIO_DETECTOR_VERSION
    )


class CorrectionService:
    """Thin façade delegating to the five CorrectionsStudio* services."""

    def __init__(self, db_session: Any = None) -> None:
        self.db_session = db_session
        self.repo = _STORE
        self._session_svc = CorrectionsStudioSessionService(self.repo)
        self._candidate_svc = CorrectionsStudioCandidateService(self._session_svc)
        self._review_svc = CorrectionsStudioReviewService(self._session_svc)
        self._preview_svc = CorrectionsStudioPreviewService(self._session_svc)
        self._export_svc = CorrectionsStudioExportService(
            self._session_svc, self._preview_svc
        )

    def start_or_resume_session(self, transcript_path: str) -> Dict[str, Any]:
        normalized = normalize_transcript_path(transcript_path)
        segments = load_segments(normalized)
        fingerprint = compute_transcript_identity_hash(segments)
        existing_raw = self.repo.read(normalized)
        if existing_raw:
            doc = normalize_cutover_session_blob(existing_raw)
            if doc.recorded_transcript_identity_hash == fingerprint:
                return _document_to_api_dict(doc)

        session_id = f"corrections_{Path(normalized).stem}_{fingerprint[:8]}"
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        doc = StudioSessionDocument(
            studio_schema_version=1,
            session_id=session_id,
            transcript_path=normalized,
            recorded_transcript_identity_hash=fingerprint,
            created_at=now,
            updated_at=now,
        )
        seq = self._session_svc.next_event_sequence(session_id)
        payload = SessionStartedPayload(
            transcript_path=normalized,
            recorded_transcript_identity_hash=fingerprint,
        )
        event = StudioEventEnvelope(
            session_id=session_id,
            event_type="session_started",
            event_sequence=seq,
            payload=payload.model_dump(mode="json"),
        )
        self._session_svc.persist(normalized, doc, event)
        studio_metrics.increment("sessions_started")
        return _document_to_api_dict(doc)

    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        raw = self.repo.find_by_session_id(session_id)
        if not raw:
            return None
        doc = normalize_cutover_session_blob(raw)
        return _document_to_api_dict(doc)

    def generate_candidates(
        self, session_id: str, force: bool = False
    ) -> List[Dict[str, Any]]:
        rows = self._candidate_svc.generate_candidates(session_id, force=force)
        studio_metrics.increment("candidates_generated")
        return [c.model_dump(mode="json") for c in rows]

    def list_candidates(
        self,
        session_id: str,
        status_filter: Optional[str] = None,
        kind_filter: Optional[List[str]] = None,
        confidence_min: Optional[float] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        doc = self._session_svc.load_document(session_id)
        candidates = list(doc.candidates)
        if status_filter:
            candidates = [
                c for c in candidates if c.review_status.value == status_filter
            ]
        if kind_filter:
            candidates = [c for c in candidates if c.kind in kind_filter]
        if confidence_min is not None:
            candidates = [c for c in candidates if c.confidence >= confidence_min]
        sliced = candidates[offset : offset + limit]
        return [c.model_dump(mode="json") for c in sliced]

    def count_candidates(
        self,
        session_id: str,
        status_filter: Optional[str] = None,
        kind_filter: Optional[List[str]] = None,
        confidence_min: Optional[float] = None,
    ) -> int:
        return len(
            self.list_candidates(
                session_id,
                status_filter=status_filter,
                kind_filter=kind_filter,
                confidence_min=confidence_min,
                offset=0,
                limit=10_000,
            )
        )

    def record_decision(
        self,
        session_id: str,
        candidate_id: str,
        decision: str,
        selected_occurrence_keys: Optional[List[str]] = None,
        learn_rule_params: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._review_svc.record_decision(
            session_id,
            candidate_id,
            decision,
            selected_occurrence_keys=selected_occurrence_keys,
            learn_rule_params=learn_rule_params,
        )
        studio_metrics.increment("reviews_recorded")

    def compute_preview(self, session_id: str) -> Dict[str, Any]:
        out = self._preview_svc.compute_preview(session_id)
        studio_metrics.increment("previews_computed")
        return out

    def apply_and_export(
        self, session_id: str, export_path: Optional[str] = None
    ) -> Dict[str, Any]:
        result = self._export_svc.apply_and_export(session_id, export_path=export_path)
        studio_metrics.increment("exports_completed")
        return result

    def get_candidate_local_diff(
        self, session_id: str, candidate_id: str
    ) -> Dict[str, Any]:
        doc = self._session_svc.load_document(session_id)
        candidate = next(
            (c for c in doc.candidates if c.candidate_id == candidate_id),
            None,
        )
        if not candidate:
            return {"diffs": []}

        diffs = []
        for occ in candidate.occurrences:
            snippet = occ.snippet or ""
            wrong = candidate.wrong_text
            suggested = candidate.right_text
            before = snippet
            after = (
                snippet.replace(wrong, suggested, 1) if wrong in snippet else snippet
            )
            diffs.append(
                {
                    "segment_id": occ.segment_id,
                    "segment_index": occ.segment_index,
                    "speaker": occ.speaker,
                    "time_start": occ.time_start,
                    "time_end": occ.time_end,
                    "before": before,
                    "after": after,
                    "stable_occurrence_key": occ.stable_occurrence_key,
                }
            )
        return {"diffs": diffs}

    def get_session_stats(self, session_id: str) -> Dict[str, int]:
        doc = self._session_svc.load_document(session_id)
        stats = {"pending": 0, "accepted": 0, "rejected": 0, "skipped": 0}
        for candidate in doc.candidates:
            status = candidate.review_status.value
            if status in stats:
                stats[status] += 1
            else:
                stats["pending"] += 1
        return stats
