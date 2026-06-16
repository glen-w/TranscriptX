"""Integration-style tests: fake session store, JSONL replay, review → reconcile."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import pytest

from transcriptx.services.corrections_studio.normalize import (
    session_document_to_persistence,
)
from transcriptx.services.corrections_studio.reconcile import (
    parse_events_jsonl,
    reconcile_snapshot_from_events,
)
from transcriptx.services.corrections_studio.review_service import (
    CorrectionsStudioReviewService,
)
from transcriptx.services.corrections_studio.schema import (
    GenerationManifest,
    ReviewAction,
    ReviewStatus,
    StudioEventEnvelope,
)
from transcriptx.services.corrections_studio.session_service import (
    CorrectionsStudioSessionService,
)


class FakeCorrectionsSessionStore:
    """Minimal in-memory store for session_service + review_service tests."""

    def __init__(self) -> None:
        self._lines: Dict[str, List[str]] = {}
        self._blob_by_session: Dict[str, Dict[str, Any]] = {}

    def seed_events(self, session_id: str, lines: List[str]) -> None:
        self._lines[session_id] = list(lines)

    def seed_blob(self, session_id: str, blob: Dict[str, Any]) -> None:
        self._blob_by_session[session_id] = dict(blob)

    def read_event_lines(self, session_id: str) -> List[str]:
        return list(self._lines.get(session_id, []))

    def find_by_session_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        b = self._blob_by_session.get(session_id)
        return dict(b) if b is not None else None

    def write_and_append_event(
        self,
        transcript_path: str,
        session_dict: Dict[str, Any],
        event_obj: Dict[str, Any],
        *,
        timeout: int = 15,
    ) -> None:
        _ = transcript_path, timeout
        sid = str(session_dict["session_id"])
        line = json.dumps(event_obj, ensure_ascii=False, separators=(",", ":"))
        self._lines.setdefault(sid, []).append(line)
        self._blob_by_session[sid] = dict(session_dict)


def _cand(cid: str, gen: int, *, wrong: str = "w", right: str = "r") -> dict:
    return {
        "candidate_id": cid,
        "generation_id": gen,
        "kind": "acronym",
        "wrong_text": wrong,
        "right_text": right,
        "confidence": 0.5,
        "occurrences": [],
        "review_status": "pending",
    }


def _events_session_candidates_review(
    ts: str = "2026-01-01T00:00:00Z",
) -> List[StudioEventEnvelope]:
    e1 = StudioEventEnvelope(
        session_id="sid",
        event_type="session_started",
        event_sequence=1,
        timestamp=ts,
        payload={
            "transcript_path": "/t.json",
            "recorded_transcript_identity_hash": "fh",
        },
    )
    e2 = StudioEventEnvelope(
        session_id="sid",
        event_type="candidates_generated",
        event_sequence=2,
        timestamp=ts,
        payload={"generation_id": 1, "candidates": [_cand("c1", 1)]},
    )
    e3 = StudioEventEnvelope(
        session_id="sid",
        event_type="review_recorded",
        event_sequence=3,
        timestamp=ts,
        payload={
            "generation_id": 1,
            "candidate_id": "c1",
            "review_action": "reject",
            "apply_scope": "all",
        },
    )
    return [e1, e2, e3]


@pytest.mark.unit
def test_parse_events_jsonl_round_trip_matches_direct_reconcile() -> None:
    events = _events_session_candidates_review()
    lines = [json.dumps(e.model_dump(mode="json")) for e in events]
    parsed = parse_events_jsonl(lines)
    via_jsonl = reconcile_snapshot_from_events(events=parsed)
    direct = reconcile_snapshot_from_events(events=events)
    assert via_jsonl.model_dump() == direct.model_dump()


@pytest.mark.unit
def test_reconcile_interleaved_noop_events_same_state_updated_at_follows_last_envelope() -> (
    None
):
    """Unknown event_type strings are not representable on StudioEventEnvelope; no-op types exercise noop replay and last_env."""
    ts = "2026-01-01T00:00:00Z"
    ts_noop = "2026-01-10T00:00:00Z"
    base = _events_session_candidates_review(ts=ts)
    noop_last = StudioEventEnvelope(
        session_id="sid",
        event_type="preview_computed",
        event_sequence=4,
        timestamp=ts_noop,
        payload={},
    )
    with_noop = [base[0], base[1], base[2], noop_last]
    without_noop = list(base)
    d1 = reconcile_snapshot_from_events(events=with_noop)
    d0 = reconcile_snapshot_from_events(events=without_noop)
    assert d1.current_generation_id == d0.current_generation_id
    assert len(d1.candidates) == len(d0.candidates)
    assert d1.candidates[0].review_status == d0.candidates[0].review_status
    assert len(d1.review_records) == len(d0.review_records)
    assert d1.updated_at == ts_noop


@pytest.mark.unit
def test_second_candidates_generated_without_manifest_retains_prior_current_generation_blob() -> (
    None
):
    ts = "2026-01-01T00:00:00Z"
    man = GenerationManifest(transcript_identity_hash="fh", detector_version="d1")
    e1 = StudioEventEnvelope(
        session_id="sid",
        event_type="session_started",
        event_sequence=1,
        timestamp=ts,
        payload={
            "transcript_path": "/t.json",
            "recorded_transcript_identity_hash": "fh",
        },
    )
    e2 = StudioEventEnvelope(
        session_id="sid",
        event_type="candidates_generated",
        event_sequence=2,
        timestamp=ts,
        payload={
            "generation_id": 1,
            "generation_manifest": man.model_dump(mode="json"),
            "generation_manifest_hash": "mh1",
            "candidate_ids": ["a"],
            "candidates": [_cand("a", 1)],
        },
    )
    e3 = StudioEventEnvelope(
        session_id="sid",
        event_type="candidates_generated",
        event_sequence=3,
        timestamp=ts,
        payload={
            "generation_id": 2,
            "candidates": [_cand("b", 2, wrong="x", right="y")],
        },
    )
    doc = reconcile_snapshot_from_events(events=[e1, e2, e3])
    assert doc.current_generation_id == 2
    assert len(doc.candidates) == 1
    assert doc.candidates[0].candidate_id == "b"
    assert doc.current_generation is not None
    assert doc.current_generation.generation_id == 1
    assert doc.current_generation.generation_manifest_hash == "mh1"


@pytest.mark.unit
def test_session_service_reconcile_from_events_matches_reconcile_snapshot() -> None:
    events = _events_session_candidates_review()
    lines = [json.dumps(e.model_dump(mode="json")) for e in events]
    store = FakeCorrectionsSessionStore()
    store.seed_events("sid", lines)
    svc = CorrectionsStudioSessionService(store=store)
    doc = svc.reconcile_from_events("sid")
    expected = reconcile_snapshot_from_events(events=events)
    assert doc.model_dump() == expected.model_dump()


@pytest.mark.unit
def test_record_decision_then_reconcile_from_events() -> None:
    events_pre = _events_session_candidates_review()[:2]
    doc_pre = reconcile_snapshot_from_events(events=events_pre)
    blob = session_document_to_persistence(doc_pre)
    lines = [json.dumps(e.model_dump(mode="json")) for e in events_pre]

    store = FakeCorrectionsSessionStore()
    store.seed_events("sid", lines)
    store.seed_blob("sid", blob)

    session_svc = CorrectionsStudioSessionService(store=store)
    review_svc = CorrectionsStudioReviewService(session_svc)
    review_svc.record_decision("sid", "c1", "reject")

    doc = session_svc.reconcile_from_events("sid")
    assert doc.candidates[0].review_status == ReviewStatus.rejected
    assert len(doc.review_records) == 1
    assert doc.review_records[0].review_action == ReviewAction.reject
