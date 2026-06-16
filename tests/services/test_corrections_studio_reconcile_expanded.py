"""Expanded replay tests: matrix cases + compact golden fixture."""

from __future__ import annotations

from transcriptx.services.corrections_studio.reconcile import (
    reconcile_snapshot_from_events,
)
from transcriptx.services.corrections_studio.schema import (
    GenerationManifest,
    ReviewAction,
    ReviewStatus,
    StudioEventEnvelope,
)


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


def test_reconcile_golden_multi_generation_with_reviews() -> None:
    t1, t2, t3, t4, t5 = (
        "2026-01-01T10:00:00Z",
        "2026-01-01T11:00:00Z",
        "2026-01-01T12:00:00Z",
        "2026-01-02T10:00:00Z",
        "2026-01-02T11:00:00Z",
    )
    man = GenerationManifest(transcript_identity_hash="fh", detector_version="d1")
    e1 = StudioEventEnvelope(
        session_id="sid",
        event_type="session_started",
        event_sequence=1,
        timestamp=t1,
        payload={
            "transcript_path": "/t.json",
            "recorded_transcript_identity_hash": "fh",
        },
    )
    e2 = StudioEventEnvelope(
        session_id="sid",
        event_type="candidates_generated",
        event_sequence=2,
        timestamp=t2,
        payload={
            "generation_id": 1,
            "generation_manifest": man.model_dump(mode="json"),
            "generation_manifest_hash": "mh1",
            "candidate_ids": ["c1"],
            "candidates": [_cand("c1", 1)],
        },
    )
    e3 = StudioEventEnvelope(
        session_id="sid",
        event_type="review_recorded",
        event_sequence=3,
        timestamp=t3,
        payload={
            "generation_id": 1,
            "candidate_id": "c1",
            "review_action": "accept",
            "apply_scope": "all",
        },
    )
    e4 = StudioEventEnvelope(
        session_id="sid",
        event_type="candidates_generated",
        event_sequence=4,
        timestamp=t4,
        payload={
            "generation_id": 2,
            "generation_manifest": man.model_dump(mode="json"),
            "generation_manifest_hash": "mh2",
            "candidate_ids": ["c2"],
            "candidates": [_cand("c2", 2, wrong="a", right="b")],
        },
    )
    e5 = StudioEventEnvelope(
        session_id="sid",
        event_type="review_recorded",
        event_sequence=5,
        timestamp=t5,
        payload={
            "generation_id": 2,
            "candidate_id": "c2",
            "review_action": "reject",
            "apply_scope": "all",
        },
    )
    doc = reconcile_snapshot_from_events(events=[e1, e2, e3, e4, e5])
    assert doc.session_id == "sid"
    assert doc.current_generation_id == 2
    assert doc.updated_at == t5
    assert doc.current_generation is not None
    assert doc.current_generation.generation_manifest_hash == "mh2"
    assert doc.current_generation.generation_id == 2
    assert len(doc.candidates) == 1
    assert doc.candidates[0].candidate_id == "c2"
    assert doc.candidates[0].review_status == ReviewStatus.rejected
    assert len(doc.review_records) == 2
    assert doc.review_records[0].generation_id == 1
    assert doc.review_records[0].candidate_id == "c1"
    assert doc.review_records[0].review_action == ReviewAction.accept
    assert doc.review_records[1].generation_id == 2
    assert doc.review_records[1].candidate_id == "c2"
    assert doc.review_records[1].review_action == ReviewAction.reject


def test_reconcile_two_generations_without_intervening_reviews() -> None:
    ts = "2026-01-01T00:00:00Z"
    man = GenerationManifest(transcript_identity_hash="fh", detector_version="d1")
    e1 = StudioEventEnvelope(
        session_id="s",
        event_type="session_started",
        event_sequence=1,
        timestamp=ts,
        payload={
            "transcript_path": "/p.json",
            "recorded_transcript_identity_hash": "fh",
        },
    )
    e2 = StudioEventEnvelope(
        session_id="s",
        event_type="candidates_generated",
        event_sequence=2,
        timestamp=ts,
        payload={
            "generation_id": 1,
            "generation_manifest": man.model_dump(mode="json"),
            "generation_manifest_hash": "m1",
            "candidate_ids": ["a"],
            "candidates": [_cand("a", 1)],
        },
    )
    e3 = StudioEventEnvelope(
        session_id="s",
        event_type="candidates_generated",
        event_sequence=3,
        timestamp=ts,
        payload={
            "generation_id": 2,
            "generation_manifest": man.model_dump(mode="json"),
            "generation_manifest_hash": "m2",
            "candidate_ids": ["b"],
            "candidates": [_cand("b", 2, wrong="x", right="y")],
        },
    )
    doc = reconcile_snapshot_from_events(events=[e1, e2, e3])
    assert doc.current_generation_id == 2
    assert len(doc.candidates) == 1
    assert doc.candidates[0].candidate_id == "b"
    assert doc.review_records == []


def test_reconcile_out_of_order_matches_sorted_replay() -> None:
    ts = "2026-01-01T00:00:00Z"
    e1 = StudioEventEnvelope(
        session_id="s",
        event_type="session_started",
        event_sequence=1,
        timestamp=ts,
        payload={
            "transcript_path": "/p.json",
            "recorded_transcript_identity_hash": "fh",
        },
    )
    e2 = StudioEventEnvelope(
        session_id="s",
        event_type="candidates_generated",
        event_sequence=2,
        timestamp=ts,
        payload={"generation_id": 1, "candidates": [_cand("c1", 1)]},
    )
    e3 = StudioEventEnvelope(
        session_id="s",
        event_type="review_recorded",
        event_sequence=3,
        timestamp=ts,
        payload={
            "generation_id": 1,
            "candidate_id": "c1",
            "review_action": "skip",
            "apply_scope": "all",
        },
    )
    ordered = reconcile_snapshot_from_events(events=[e1, e2, e3])
    shuffled = reconcile_snapshot_from_events(events=[e3, e1, e2])
    assert ordered.model_dump() == shuffled.model_dump()


def test_reconcile_second_review_same_candidate_replaces_first() -> None:
    ts = "2026-01-01T00:00:00Z"
    e1 = StudioEventEnvelope(
        session_id="s",
        event_type="session_started",
        event_sequence=1,
        timestamp=ts,
        payload={
            "transcript_path": "/p.json",
            "recorded_transcript_identity_hash": "fh",
        },
    )
    e2 = StudioEventEnvelope(
        session_id="s",
        event_type="candidates_generated",
        event_sequence=2,
        timestamp=ts,
        payload={"generation_id": 1, "candidates": [_cand("c1", 1)]},
    )
    e3 = StudioEventEnvelope(
        session_id="s",
        event_type="review_recorded",
        event_sequence=3,
        timestamp=ts,
        payload={
            "generation_id": 1,
            "candidate_id": "c1",
            "review_action": "skip",
            "apply_scope": "all",
        },
    )
    e4 = StudioEventEnvelope(
        session_id="s",
        event_type="review_recorded",
        event_sequence=4,
        timestamp=ts,
        payload={
            "generation_id": 1,
            "candidate_id": "c1",
            "review_action": "accept",
            "apply_scope": "all",
        },
    )
    doc = reconcile_snapshot_from_events(events=[e1, e2, e3, e4])
    assert len(doc.review_records) == 1
    assert doc.review_records[0].review_action == ReviewAction.accept
    assert doc.review_records[0].event_sequence == 4
    assert doc.candidates[0].review_status == ReviewStatus.accepted


def test_reconcile_new_generation_drops_reviews_for_that_generation_id() -> None:
    ts = "2026-01-01T00:00:00Z"
    e1 = StudioEventEnvelope(
        session_id="s",
        event_type="session_started",
        event_sequence=1,
        timestamp=ts,
        payload={
            "transcript_path": "/p.json",
            "recorded_transcript_identity_hash": "fh",
        },
    )
    e2 = StudioEventEnvelope(
        session_id="s",
        event_type="candidates_generated",
        event_sequence=2,
        timestamp=ts,
        payload={"generation_id": 1, "candidates": [_cand("c1", 1)]},
    )
    e3 = StudioEventEnvelope(
        session_id="s",
        event_type="review_recorded",
        event_sequence=3,
        timestamp=ts,
        payload={
            "generation_id": 2,
            "candidate_id": "c1",
            "review_action": "accept",
            "apply_scope": "all",
        },
    )
    e4 = StudioEventEnvelope(
        session_id="s",
        event_type="candidates_generated",
        event_sequence=4,
        timestamp=ts,
        payload={"generation_id": 2, "candidates": [_cand("c2", 2)]},
    )
    doc = reconcile_snapshot_from_events(events=[e1, e2, e3, e4])
    assert doc.current_generation_id == 2
    assert len(doc.review_records) == 0
