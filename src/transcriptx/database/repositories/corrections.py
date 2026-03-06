"""Repository for Correction Studio persistence."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import func as sa_func

from transcriptx.core.utils.logger import get_logger
from transcriptx.database.models.corrections import (
    CorrectionCandidate,
    CorrectionDecision,
    CorrectionRuleDB,
    CorrectionSession,
)
from .base import BaseRepository

logger = get_logger()


def _session_to_dict(model: CorrectionSession) -> Dict[str, Any]:
    return {
        "id": model.id,
        "transcript_file_id": model.transcript_file_id,
        "transcript_path": model.transcript_path,
        "source_fingerprint": model.source_fingerprint,
        "detector_version": model.detector_version,
        "status": model.status,
        "ui_state_json": model.ui_state_json,
        "created_at": model.created_at,
        "updated_at": model.updated_at,
    }


def _candidate_to_dict(model: CorrectionCandidate) -> Dict[str, Any]:
    return {
        "id": model.id,
        "session_id": model.session_id,
        "candidate_hash": model.candidate_hash,
        "kind": model.kind,
        "wrong_text": model.wrong_text,
        "suggested_text": model.suggested_text,
        "confidence": model.confidence,
        "rule_id": model.rule_id,
        "occurrences_json": model.occurrences_json,
        "evidence_json": model.evidence_json,
        "status": model.status,
        "created_at": model.created_at,
    }


def _decision_to_dict(model: CorrectionDecision) -> Dict[str, Any]:
    return {
        "id": model.id,
        "session_id": model.session_id,
        "candidate_id": model.candidate_id,
        "decision": model.decision,
        "selected_occurrence_ids_json": model.selected_occurrence_ids_json,
        "created_rule_id": model.created_rule_id,
        "note": model.note,
        "actor": model.actor,
        "created_at": model.created_at,
        "updated_at": model.updated_at,
    }


def _rule_to_dict(model: CorrectionRuleDB) -> Dict[str, Any]:
    return {
        "id": model.id,
        "rule_hash": model.rule_hash,
        "scope": model.scope,
        "rule_type": model.rule_type,
        "wrong_variants_json": model.wrong_variants_json,
        "replacement_text": model.replacement_text,
        "confidence": model.confidence,
        "auto_apply": model.auto_apply,
        "conditions_json": model.conditions_json,
        "is_person_name": model.is_person_name,
        "enabled": model.enabled,
        "source_session_id": model.source_session_id,
        "transcript_path": model.transcript_path,
        "created_at": model.created_at,
        "updated_at": model.updated_at,
    }


# Allowed enum values for validation
_VALID_SESSION_STATUSES = {"active", "completed", "abandoned"}
_VALID_CANDIDATE_STATUSES = {"pending", "accepted", "rejected", "skipped"}
_VALID_DECISIONS = {"accept", "reject", "skip"}


class CorrectionRepository(BaseRepository):
    """CRUD operations for correction studio tables. All returns are dicts."""

    # -- Sessions --

    def find_active_session(
        self, transcript_path: str, source_fingerprint: str
    ) -> Optional[Dict[str, Any]]:
        model = (
            self.session.query(CorrectionSession)
            .filter(
                CorrectionSession.transcript_path == transcript_path,
                CorrectionSession.source_fingerprint == source_fingerprint,
                CorrectionSession.status == "active",
            )
            .order_by(CorrectionSession.created_at.desc())
            .first()
        )
        if model is None:
            return None
        return _session_to_dict(model)

    def find_active_session_by_path(
        self, transcript_path: str
    ) -> Optional[Dict[str, Any]]:
        """Return the most recent active session for this path (any fingerprint)."""
        model = (
            self.session.query(CorrectionSession)
            .filter(
                CorrectionSession.transcript_path == transcript_path,
                CorrectionSession.status == "active",
            )
            .order_by(CorrectionSession.created_at.desc())
            .first()
        )
        if model is None:
            return None
        return _session_to_dict(model)

    def create_session(self, **kwargs: Any) -> Dict[str, Any]:
        kwargs.setdefault("id", str(uuid4()))
        model = CorrectionSession(**kwargs)
        self.session.add(model)
        self.session.flush()
        return _session_to_dict(model)

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        model = (
            self.session.query(CorrectionSession)
            .filter(CorrectionSession.id == session_id)
            .first()
        )
        if model is None:
            return None
        return _session_to_dict(model)

    def update_session_status(self, session_id: str, status: str) -> None:
        if status not in _VALID_SESSION_STATUSES:
            raise ValueError(
                f"Invalid session status: {status}. Must be one of {_VALID_SESSION_STATUSES}"
            )
        model = (
            self.session.query(CorrectionSession)
            .filter(CorrectionSession.id == session_id)
            .first()
        )
        if model:
            model.status = status
            self.session.flush()

    def update_session_ui_state(self, session_id: str, ui_state_json: Any) -> None:
        model = (
            self.session.query(CorrectionSession)
            .filter(CorrectionSession.id == session_id)
            .first()
        )
        if model:
            model.ui_state_json = ui_state_json
            self.session.flush()

    # -- Candidates --

    def bulk_create_candidates(
        self, session_id: str, candidates_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for data in candidates_data:
            data.setdefault("id", str(uuid4()))
            data["session_id"] = session_id
            model = CorrectionCandidate(**data)
            self.session.add(model)
            self.session.flush()
            results.append(_candidate_to_dict(model))
        return results

    def list_candidates(
        self,
        session_id: str,
        status_filter: Optional[str] = None,
        kind_filter: Optional[List[str]] = None,
        confidence_min: Optional[float] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        query = self.session.query(CorrectionCandidate).filter(
            CorrectionCandidate.session_id == session_id
        )
        if status_filter:
            query = query.filter(CorrectionCandidate.status == status_filter)
        if kind_filter:
            query = query.filter(CorrectionCandidate.kind.in_(kind_filter))
        if confidence_min is not None:
            query = query.filter(CorrectionCandidate.confidence >= confidence_min)
        query = query.order_by(CorrectionCandidate.created_at)
        query = query.offset(offset).limit(limit)
        return [_candidate_to_dict(m) for m in query.all()]

    def count_candidates(
        self,
        session_id: str,
        status_filter: Optional[str] = None,
        kind_filter: Optional[List[str]] = None,
        confidence_min: Optional[float] = None,
    ) -> int:
        query = self.session.query(CorrectionCandidate).filter(
            CorrectionCandidate.session_id == session_id
        )
        if status_filter:
            query = query.filter(CorrectionCandidate.status == status_filter)
        if kind_filter:
            query = query.filter(CorrectionCandidate.kind.in_(kind_filter))
        if confidence_min is not None:
            query = query.filter(CorrectionCandidate.confidence >= confidence_min)
        return query.count()

    def get_candidate(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        model = (
            self.session.query(CorrectionCandidate)
            .filter(CorrectionCandidate.id == candidate_id)
            .first()
        )
        if model is None:
            return None
        return _candidate_to_dict(model)

    def update_candidate_status(self, candidate_id: str, status: str) -> None:
        if status not in _VALID_CANDIDATE_STATUSES:
            raise ValueError(
                f"Invalid candidate status: {status}. Must be one of {_VALID_CANDIDATE_STATUSES}"
            )
        model = (
            self.session.query(CorrectionCandidate)
            .filter(CorrectionCandidate.id == candidate_id)
            .first()
        )
        if model:
            model.status = status
            self.session.flush()

    def delete_candidates_for_session(self, session_id: str) -> int:
        count = (
            self.session.query(CorrectionCandidate)
            .filter(CorrectionCandidate.session_id == session_id)
            .delete(synchronize_session="fetch")
        )
        self.session.flush()
        return count

    # -- Decisions --

    def upsert_decision(
        self, session_id: str, candidate_id: str, **decision_kwargs: Any
    ) -> Dict[str, Any]:
        decision = decision_kwargs.get("decision")
        if decision is not None and decision not in _VALID_DECISIONS:
            raise ValueError(
                f"Invalid decision: {decision}. Must be one of {_VALID_DECISIONS}"
            )
        existing = (
            self.session.query(CorrectionDecision)
            .filter(
                CorrectionDecision.session_id == session_id,
                CorrectionDecision.candidate_id == candidate_id,
            )
            .first()
        )
        if existing:
            for key, value in decision_kwargs.items():
                setattr(existing, key, value)
            self.session.flush()
            return _decision_to_dict(existing)

        model = CorrectionDecision(
            id=str(uuid4()),
            session_id=session_id,
            candidate_id=candidate_id,
            **decision_kwargs,
        )
        self.session.add(model)
        self.session.flush()
        return _decision_to_dict(model)

    def get_decisions_for_session(self, session_id: str) -> List[Dict[str, Any]]:
        models = (
            self.session.query(CorrectionDecision)
            .filter(CorrectionDecision.session_id == session_id)
            .order_by(CorrectionDecision.created_at)
            .all()
        )
        return [_decision_to_dict(m) for m in models]

    # -- Rules --

    def create_rule(self, **kwargs: Any) -> Dict[str, Any]:
        kwargs.setdefault("id", str(uuid4()))
        # Use sentinel for global scope so unique(rule_hash, scope, transcript_path) works (NULL != NULL in most DBs)
        if kwargs.get("scope") == "global" and kwargs.get("transcript_path") is None:
            kwargs["transcript_path"] = "__global__"
        model = CorrectionRuleDB(**kwargs)
        self.session.add(model)
        self.session.flush()
        return _rule_to_dict(model)

    def get_rule(self, rule_id: str) -> Optional[Dict[str, Any]]:
        model = (
            self.session.query(CorrectionRuleDB)
            .filter(CorrectionRuleDB.id == rule_id)
            .first()
        )
        return _rule_to_dict(model) if model else None

    def find_enabled_rules(
        self, scope: str, transcript_path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        query = self.session.query(CorrectionRuleDB).filter(
            CorrectionRuleDB.enabled == True,  # noqa: E712
            CorrectionRuleDB.scope == scope,
        )
        if scope == "transcript" and transcript_path:
            query = query.filter(CorrectionRuleDB.transcript_path == transcript_path)
        elif scope == "global":
            pass
        models = query.all()
        return [_rule_to_dict(m) for m in models]

    # -- Stats --

    def get_session_stats(self, session_id: str) -> Dict[str, int]:
        rows = (
            self.session.query(
                CorrectionCandidate.status,
                sa_func.count(CorrectionCandidate.id),
            )
            .filter(CorrectionCandidate.session_id == session_id)
            .group_by(CorrectionCandidate.status)
            .all()
        )
        stats = {"pending": 0, "accepted": 0, "rejected": 0, "skipped": 0}
        for status, count in rows:
            stats[status] = count
        return stats
