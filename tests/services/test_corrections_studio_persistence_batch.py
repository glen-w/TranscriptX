"""Persistence batching, concurrency, and rule replay for Corrections Studio."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.core.store import corrections_session_store as cs
from transcriptx.core.store.corrections_session_store import GenerationCommitConflict
from transcriptx.services.corrections_studio.normalize import (
    normalize_cutover_session_blob,
)
from transcriptx.services.corrections_studio.reconcile import (
    reconcile_snapshot_from_events,
)
from transcriptx.services.corrections_studio.schema import (
    RuleLifecycleState,
    RuleStateChangedPayload,
    StudioEventEnvelope,
    StudioRule,
)


@pytest.fixture
def iso_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "corrections"
    monkeypatch.setattr(cs, "_CORRECTIONS_ROOT", root)
    return root


def _base_session(transcript_path: str, session_id: str = "sess_batch") -> dict:
    return {
        "studio_schema_version": 2,
        "session_id": session_id,
        "transcript_path": transcript_path,
        "recorded_transcript_identity_hash": "abc",
        "current_generation_id": 1,
        "candidates": [],
        "review_records": [],
        "rules": {},
        "status": "active",
        "created_at": "2020-01-01T00:00:00Z",
        "updated_at": "2020-01-01T00:00:00Z",
    }


@pytest.mark.unit
def test_event_batch_writes_all_or_snapshot_aligned(
    iso_root: Path, tmp_path: Path
) -> None:
    tjson = tmp_path / "t.json"
    tjson.write_text("{}", encoding="utf-8")
    tp = str(tjson.resolve())
    store = cs.CorrectionsSessionStore()
    sid = "sess_batch"
    session = _base_session(tp, sid)
    store.write(tp, session)

    events = [
        {
            "session_id": sid,
            "event_type": "candidates_generated",
            "event_sequence": 0,
            "payload": {"generation_id": 2, "candidate_ids": [], "candidates": []},
        },
        {
            "session_id": sid,
            "event_type": "review_recorded",
            "event_sequence": 0,
            "payload": {
                "generation_id": 2,
                "candidate_id": "c1",
                "review_action": "accept",
            },
        },
    ]
    session["current_generation_id"] = 2
    assigned = store.write_snapshot_and_event_batch(
        tp,
        session,
        events,
        allocate_sequences=True,
        expected_last_event_sequence=0,
        expected_current_generation_id=1,
        check_generation_id=True,
    )
    assert [e["event_sequence"] for e in assigned] == [1, 2]
    lines = store.read_event_lines(sid)
    assert len(lines) == 2
    loaded = store.find_by_session_id(sid)
    assert loaded["current_generation_id"] == 2


@pytest.mark.unit
def test_batch_aborts_on_sequence_conflict(iso_root: Path, tmp_path: Path) -> None:
    tjson = tmp_path / "t2.json"
    tjson.write_text("{}", encoding="utf-8")
    tp = str(tjson.resolve())
    store = cs.CorrectionsSessionStore()
    sid = "sess_conflict"
    session = _base_session(tp, sid)
    store.write(tp, session)
    store.append_event_jsonl(
        sid,
        {
            "event_sequence": 1,
            "event_type": "session_started",
            "session_id": sid,
            "payload": {},
        },
    )

    with pytest.raises(GenerationCommitConflict):
        store.write_snapshot_and_event_batch(
            tp,
            session,
            [
                {
                    "session_id": sid,
                    "event_type": "export_completed",
                    "event_sequence": 0,
                    "payload": {},
                }
            ],
            allocate_sequences=True,
            expected_last_event_sequence=0,
            check_generation_id=False,
        )


@pytest.mark.unit
def test_index_failure_does_not_corrupt_session(
    iso_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tjson = tmp_path / "t3.json"
    tjson.write_text("{}", encoding="utf-8")
    tp = str(tjson.resolve())
    store = cs.CorrectionsSessionStore()
    sid = "sess_idx"
    session = _base_session(tp, sid)
    store.write(tp, session)

    def boom(*_a, **_k):
        raise OSError("index down")

    monkeypatch.setattr(store, "_update_index_entry", boom)
    store.write_snapshot_and_event_batch(
        tp,
        {**session, "status": "active2"},
        [
            {
                "session_id": sid,
                "event_type": "export_completed",
                "event_sequence": 0,
                "payload": {},
            }
        ],
        allocate_sequences=True,
    )
    loaded = store.find_by_session_id(sid)
    assert loaded is not None
    assert loaded["status"] == "active2"
    assert len(store.read_event_lines(sid)) == 1


@pytest.mark.unit
def test_rule_state_changed_replays(iso_root: Path) -> None:
    rule = StudioRule(
        rule_id="r1",
        rule_type="phrase",
        wrong_variants=["foo"],
        replacement_text="bar",
        lifecycle=RuleLifecycleState.session_active,
    )
    events = [
        StudioEventEnvelope(
            session_id="s",
            event_type="session_started",
            event_sequence=1,
            payload={
                "transcript_path": "/t.json",
                "recorded_transcript_identity_hash": "h",
            },
        ),
        StudioEventEnvelope(
            session_id="s",
            event_type="rule_state_changed",
            event_sequence=2,
            payload=RuleStateChangedPayload(
                rule_id="r1", change="upsert", rule=rule.model_dump(mode="json")
            ).model_dump(mode="json"),
        ),
        StudioEventEnvelope(
            session_id="s",
            event_type="rule_state_changed",
            event_sequence=3,
            payload=RuleStateChangedPayload(rule_id="r1", change="disable").model_dump(
                mode="json"
            ),
        ),
    ]
    doc = reconcile_snapshot_from_events(events=events)
    assert "r1" in doc.rules
    assert doc.rules["r1"].lifecycle == RuleLifecycleState.disabled


@pytest.mark.unit
def test_schema_v1_normalize_fills_derived_fields() -> None:
    raw = {
        "studio_schema_version": 1,
        "session_id": "legacy",
        "transcript_path": "/t.json",
        "recorded_transcript_identity_hash": "h",
        "current_generation_id": 1,
        "candidates": [
            {
                "candidate_id": "c1",
                "generation_id": 1,
                "kind": "acronym",
                "wrong_text": "a",
                "right_text": "A",
                "confidence": 0.5,
                "occurrences": [],
                "review_status": "pending",
            }
        ],
        "review_records": [],
        "rules": {},
        "created_at": "2020-01-01T00:00:00Z",
        "updated_at": "2020-01-01T00:00:00Z",
        "status": "active",
    }
    doc = normalize_cutover_session_blob(raw)
    assert doc.studio_schema_version == 1
    assert doc.candidates[0].sources
    assert doc.candidates[0].semantic_identity_key
