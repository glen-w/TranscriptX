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
        self.write_snapshot_and_event_batch(
            transcript_path, session_dict, [event_obj], timeout=timeout
        )

    def write_snapshot_and_event_batch(
        self,
        transcript_path: str,
        session_dict: Dict[str, Any],
        event_objs: List[Dict[str, Any]],
        *,
        expected_last_event_sequence: Optional[int] = None,
        expected_current_generation_id: Optional[int] = None,
        check_generation_id: bool = False,
        allocate_sequences: bool = False,
        timeout: int = 15,
        update_index: bool = True,
    ) -> List[Dict[str, Any]]:
        _ = (
            transcript_path,
            expected_current_generation_id,
            check_generation_id,
            timeout,
            update_index,
        )
        sid = str(session_dict["session_id"])
        lines = self._lines.setdefault(sid, [])
        last = 0
        for line in lines:
            try:
                last = max(last, int(json.loads(line).get("event_sequence", 0)))
            except Exception:
                continue
        if expected_last_event_sequence is not None and last != int(
            expected_last_event_sequence
        ):
            from transcriptx.core.store.corrections_session_store import (
                GenerationCommitConflict,
            )

            raise GenerationCommitConflict(
                "seq conflict", reason="event_sequence_conflict"
            )
        next_seq = last + 1 if last else 1
        assigned: List[Dict[str, Any]] = []
        for i, raw in enumerate(event_objs):
            ev = dict(raw)
            if allocate_sequences:
                ev["event_sequence"] = next_seq + i
            assigned.append(ev)
            lines.append(json.dumps(ev, ensure_ascii=False, separators=(",", ":")))
        self._blob_by_session[sid] = dict(session_dict)
        return assigned


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


@pytest.mark.unit
def test_learn_record_decision_emits_rule_and_review_events() -> None:
    events_pre = _events_session_candidates_review()[:2]
    doc_pre = reconcile_snapshot_from_events(events=events_pre)
    blob = session_document_to_persistence(doc_pre)
    lines = [json.dumps(e.model_dump(mode="json")) for e in events_pre]

    store = FakeCorrectionsSessionStore()
    store.seed_events("sid", lines)
    store.seed_blob("sid", blob)

    session_svc = CorrectionsStudioSessionService(store=store)
    review_svc = CorrectionsStudioReviewService(session_svc)
    review_svc.record_decision(
        "sid",
        "c1",
        "learn",
        learn_rule_params={
            "rule_hash": "rule_learn_1",
            "rule_type": "phrase",
            "wrong_variants_json": ["foo"],
            "replacement_text": "bar",
            "scope": "global",
            "confidence": 0.8,
            "auto_apply": False,
        },
    )

    raw_lines = store.read_event_lines("sid")
    types = [json.loads(ln)["event_type"] for ln in raw_lines]
    assert "rule_state_changed" in types
    assert "review_recorded" in types
    appended = [json.loads(ln) for ln in raw_lines[2:]]
    assert appended[0]["event_type"] == "rule_state_changed"
    assert appended[1]["event_type"] == "review_recorded"
    assert appended[1]["event_sequence"] == appended[0]["event_sequence"] + 1

    doc = session_svc.reconcile_from_events("sid")
    assert "rule_learn_1" in doc.rules
    assert doc.review_records[-1].learn_rule_id == "rule_learn_1"
    assert doc.review_records[-1].review_action == ReviewAction.learn


@pytest.mark.unit
def test_migrated_from_generation_id_survives_event_replay() -> None:
    events = list(_events_session_candidates_review()[:2])
    migrated = StudioEventEnvelope(
        session_id="sid",
        event_type="review_recorded",
        event_sequence=3,
        generation_id=1,
        payload={
            "generation_id": 1,
            "candidate_id": "c1",
            "review_action": "accept",
            "apply_scope": "all",
            "migrated_from_generation_id": 1,
        },
    )
    doc = reconcile_snapshot_from_events(events=events + [migrated])
    assert any(r.migrated_from_generation_id == 1 for r in doc.review_records)
