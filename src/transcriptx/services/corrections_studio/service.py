"""
CorrectionService: façade over CorrectionsStudio* services (pass-through).

Business logic lives in session / candidate / review / preview / export services.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from transcriptx.core.store.corrections_session_store import CorrectionsSessionStore
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.canonicalization import compute_transcript_identity_hash
from transcriptx.io import load_segments
from transcriptx.io.speaker_map_resolver import (
    SpeakerMapResolver,
    resolve_speaker_display_label,
)
from transcriptx.services.corrections_studio.candidate_service import (
    CorrectionsStudioCandidateService,
)
from transcriptx.services.corrections_studio.generation_manifest import (
    evaluate_session_staleness,
)
from transcriptx.services.corrections_studio.export_service import (
    CorrectionsStudioExportService,
)
from transcriptx.services.corrections_studio.manual_propose_service import (
    CorrectionsStudioManualProposeService,
    ManualProposeResult,
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
from transcriptx.services.corrections_studio.review_target import (
    normalize_review_target_text,
    resolve_effective_right,
)
from transcriptx.services.corrections_studio.schema import (
    CandidateLocalDiffResult,
    CandidateOccurrenceDiff,
    ReviewAction,
    SessionStartedPayload,
    StalenessStatus,
    StudioCandidate,
    StudioEventEnvelope,
    StudioExportResult,
    StudioPreviewResult,
    StudioReviewRecord,
    StudioReviewStats,
    StudioSessionDocument,
    StudioTranscriptSummary,
)
from transcriptx.services.corrections_studio.session_service import (
    CorrectionsStudioSessionService,
)
from transcriptx.services.corrections_studio import studio_metrics


def normalize_transcript_path(path: str) -> str:
    return str(Path(path).expanduser().resolve())


_STORE = CorrectionsSessionStore()
_logger = get_logger()


def _session_document_for_api(doc: StudioSessionDocument) -> StudioSessionDocument:
    status, generation_inputs_stale, _ = evaluate_session_staleness(doc)
    return doc.model_copy(
        update={
            "staleness_status": status,
            "generation_inputs_stale": generation_inputs_stale,
            "candidates_stale": status != StalenessStatus.ok,
        }
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
        self._manual_svc = CorrectionsStudioManualProposeService(self._session_svc)

    def start_or_resume_session(self, transcript_path: str) -> StudioSessionDocument:
        normalized = normalize_transcript_path(transcript_path)
        segments = load_segments(normalized)
        fingerprint = compute_transcript_identity_hash(segments)
        existing_raw = self.repo.read(normalized)
        if existing_raw:
            doc = normalize_cutover_session_blob(existing_raw)
            if doc.recorded_transcript_identity_hash == fingerprint:
                return _session_document_for_api(doc)

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
        payload = SessionStartedPayload(
            transcript_path=normalized,
            recorded_transcript_identity_hash=fingerprint,
        )
        event = StudioEventEnvelope(
            session_id=session_id,
            event_type="session_started",
            event_sequence=0,
            payload=payload.model_dump(mode="json"),
        )
        self._session_svc.persist(normalized, doc, event)
        studio_metrics.increment("sessions_started")
        return _session_document_for_api(doc)

    def load_session(self, session_id: str) -> Optional[StudioSessionDocument]:
        raw = self.repo.find_by_session_id(session_id)
        if not raw:
            return None
        doc = normalize_cutover_session_blob(raw)
        return _session_document_for_api(doc)

    def generate_candidates(self, session_id: str, force: bool = False):
        result = self._candidate_svc.generate_candidates(session_id, force=force)
        if not result.commit_aborted:
            studio_metrics.increment("candidates_generated")
        return result

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
        doc = self._session_svc.load_document(session_id)
        candidates = list(doc.candidates)
        # H13: default to current generation only (aligned with compile).
        if not include_historical:
            target_gen = (
                generation_id
                if generation_id is not None
                else doc.current_generation_id
            )
            if target_gen is None:
                candidates = []
            else:
                candidates = [c for c in candidates if c.generation_id == target_gen]
        elif generation_id is not None:
            candidates = [c for c in candidates if c.generation_id == generation_id]
        if status_filter:
            candidates = [
                c for c in candidates if c.review_status.value == status_filter
            ]
        if kind_filter:
            candidates = [c for c in candidates if c.kind in kind_filter]
        if confidence_min is not None:
            candidates = [c for c in candidates if c.confidence >= confidence_min]
        if source_filter:
            wanted = set(source_filter)
            mapped = set()
            if "memory" in wanted:
                mapped.add("detector_memory")
            if "deterministic" in wanted:
                mapped.update(
                    {
                        "detector_acronym",
                        "detector_consistency",
                        "detector_fuzzy",
                    }
                )
            if "llm" in wanted:
                mapped.add("llm_discovery")
            if "viewer" in wanted or "manual" in wanted:
                mapped.add("viewer_manual")
            mapped |= wanted
            filtered = []
            for c in candidates:
                srcs = {
                    s.value if hasattr(s, "value") else str(s)
                    for s in (c.sources or [])
                }
                if srcs & mapped:
                    filtered.append(c)
            candidates = filtered
        return candidates[offset : offset + limit]

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
        return len(
            self.list_candidates(
                session_id,
                status_filter=status_filter,
                kind_filter=kind_filter,
                confidence_min=confidence_min,
                source_filter=source_filter,
                offset=0,
                limit=10_000,
                generation_id=generation_id,
                include_historical=include_historical,
            )
        )

    def get_generation_diagnostics(self, session_id: str) -> Optional[dict]:
        doc = self._session_svc.load_document(session_id)
        if (
            not doc.current_generation
            or not doc.current_generation.generation_diagnostics
        ):
            return None
        return doc.current_generation.generation_diagnostics.model_dump(mode="json")

    def record_decision(
        self,
        session_id: str,
        candidate_id: str,
        decision: str,
        selected_occurrence_keys: Optional[List[str]] = None,
        learn_rule_params: Optional[Dict[str, Any]] = None,
        review_target_raw: Optional[str] = None,
    ) -> None:
        self._review_svc.record_decision(
            session_id,
            candidate_id,
            decision,
            selected_occurrence_keys=selected_occurrence_keys,
            learn_rule_params=learn_rule_params,
            review_target_raw=review_target_raw,
        )
        studio_metrics.increment("reviews_recorded")

    def compute_preview(self, session_id: str) -> StudioPreviewResult:
        out = self._preview_svc.compute_preview(session_id)
        studio_metrics.increment("previews_computed")
        return out

    def apply_and_export(
        self, session_id: str, export_path: Optional[str] = None
    ) -> StudioExportResult:
        result = self._export_svc.apply_and_export(session_id, export_path=export_path)
        studio_metrics.increment("exports_completed")
        return result

    def apply_and_export_scoped(
        self,
        session_id: str,
        candidate_ids: List[str],
        occurrence_keys: Optional[List[str]] = None,
        export_path: Optional[str] = None,
    ) -> StudioExportResult:
        result = self._export_svc.apply_and_export_scoped(
            session_id,
            candidate_ids=candidate_ids,
            occurrence_keys=occurrence_keys,
            export_path=export_path,
        )
        studio_metrics.increment("exports_completed")
        return result

    def propose_manual_correction(
        self,
        session_id: str,
        *,
        segment_id: Optional[str] = None,
        segment_index: Optional[int] = None,
        span: tuple[int, int],
        wrong_text: str,
        right_text: str,
        auto_accept: bool = False,
        supersede_existing: bool = False,
    ) -> ManualProposeResult:
        return self._manual_svc.propose_manual_correction(
            session_id,
            segment_id=segment_id,
            segment_index=segment_index,
            span=span,
            wrong_text=wrong_text,
            right_text=right_text,
            auto_accept=auto_accept,
            supersede_existing=supersede_existing,
        )

    def get_candidate_local_diff(
        self,
        session_id: str,
        candidate_id: str,
        transient_target_raw: Optional[str] = None,
    ) -> CandidateLocalDiffResult:
        doc = self._session_svc.load_document(session_id)
        gen = doc.current_generation_id
        candidate = next(
            (
                c
                for c in doc.candidates
                if c.candidate_id == candidate_id
                and (gen is None or c.generation_id == gen)
            ),
            None,
        )
        if not candidate:
            return CandidateLocalDiffResult()

        reviews_cur = [
            r
            for r in doc.review_records
            if r.candidate_id == candidate_id
            and (gen is None or r.generation_id == gen)
        ]
        latest: Optional[StudioReviewRecord] = None
        if reviews_cur:
            latest = max(reviews_cur, key=lambda r: r.event_sequence)

        if latest and latest.review_action in (
            ReviewAction.accept,
            ReviewAction.learn,
        ):
            suggested = resolve_effective_right(
                candidate_right_text=candidate.right_text,
                review_target_normalized=latest.review_target_text,
            )
        elif latest and latest.review_action in (
            ReviewAction.reject,
            ReviewAction.skip,
        ):
            suggested = candidate.right_text
        else:
            suggested = resolve_effective_right(
                candidate_right_text=candidate.right_text,
                review_target_normalized=normalize_review_target_text(
                    transient_target_raw
                ),
            )

        speaker_map_state = None
        try:
            speaker_map_state = SpeakerMapResolver().load_mapping(doc.transcript_path)
        except Exception:
            _logger.debug(
                "Speaker map unavailable for local diff display on %s",
                doc.transcript_path,
                exc_info=True,
            )

        diffs: List[CandidateOccurrenceDiff] = []
        for occ in candidate.occurrences:
            snippet = occ.snippet or ""
            wrong = candidate.wrong_text
            before = snippet
            after = (
                snippet.replace(wrong, suggested, 1) if wrong in snippet else snippet
            )
            diffs.append(
                CandidateOccurrenceDiff(
                    segment_id=occ.segment_id,
                    segment_index=occ.segment_index,
                    speaker=resolve_speaker_display_label(
                        occ.speaker, speaker_map_state
                    ),
                    time_start=occ.time_start,
                    time_end=occ.time_end,
                    before=before,
                    after=after,
                    stable_occurrence_key=occ.stable_occurrence_key,
                )
            )
        return CandidateLocalDiffResult(diffs=diffs)

    def get_session_stats(self, session_id: str) -> StudioReviewStats:
        doc = self._session_svc.load_document(session_id)
        gen = doc.current_generation_id
        pending = accepted = rejected = skipped = 0
        for candidate in doc.candidates:
            # H13: stats match listing — no current generation ⇒ empty counts.
            if gen is None or candidate.generation_id != gen:
                continue
            status = candidate.review_status.value
            if status == "pending":
                pending += 1
            elif status == "accepted":
                accepted += 1
            elif status == "rejected":
                rejected += 1
            elif status == "skipped":
                skipped += 1
            else:
                pending += 1
        return StudioReviewStats(
            pending=pending,
            accepted=accepted,
            rejected=rejected,
            skipped=skipped,
        )

    def list_transcript_summaries_for_studio(self) -> List[StudioTranscriptSummary]:
        """Light picker rows for Corrections Studio (no per-file segment parse)."""
        try:
            from pathlib import Path

            from transcriptx.core.utils.transcript_picker import (
                list_transcript_picker_options,
            )

            summaries: List[StudioTranscriptSummary] = []
            seen: set[str] = set()
            for opt in list_transcript_picker_options():
                try:
                    key = str(Path(opt.path).resolve())
                except OSError:
                    key = opt.path
                if key in seen:
                    continue
                seen.add(key)
                summaries.append(
                    StudioTranscriptSummary(
                        path=str(Path(opt.path)),
                        base_name=opt.label,
                        segment_count=0,
                        speaker_map_status="",
                    )
                )
            return sorted(summaries, key=lambda x: str(x.path))
        except Exception as exc:
            _logger.warning("Could not list transcripts: %s", exc)
            return []
