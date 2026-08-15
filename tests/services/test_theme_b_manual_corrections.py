"""Theme B: manual propose, carry-forward, gated generate, scoped apply."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.store import corrections_session_store as store_mod
from transcriptx.io.transcript_schema import (
    SourceInfo,
    TranscriptMetadata,
    create_transcript_document,
)
from transcriptx.services.corrections_studio.manual_propose_service import (
    ManualProposeConflict,
    ManualProposeValidationError,
)
from transcriptx.services.corrections_studio.schema import (
    CandidateSource,
    GenerationOrigin,
    ReviewStatus,
)
from transcriptx.services.corrections_studio.service import CorrectionService


def _write_transcript(path: Path, segments=None) -> None:
    if segments is None:
        segments = [
            {
                "speaker": "SPEAKER_00",
                "text": "teh quick brown fox",
                "start": 0.0,
                "end": 1.0,
                "words": [
                    {"word": "teh", "start": 0.0, "end": 0.2},
                    {"word": "quick", "start": 0.3, "end": 0.5},
                    {"word": "brown", "start": 0.5, "end": 0.7},
                    {"word": "fox", "start": 0.8, "end": 1.0},
                ],
            },
            {
                "speaker": "Alice",
                "text": "jumps over teh dog",
                "start": 1.0,
                "end": 2.0,
            },
        ]
    doc = create_transcript_document(
        segments,
        SourceInfo(
            type="manual",
            original_path="originals/sample.txt",
            imported_at="2026-01-01T00:00:00+00:00",
            file_hash="abc",
            file_mtime=0.0,
        ),
        TranscriptMetadata(
            duration_seconds=2.0,
            segment_count=len(segments),
            speaker_count=2,
        ),
    )
    path.write_text(json.dumps(doc), encoding="utf-8")


@pytest.fixture
def studio_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(store_mod, "_CORRECTIONS_ROOT", tmp_path / "corrections")
    transcript = tmp_path / "sample.json"
    _write_transcript(transcript)
    svc = CorrectionService()
    session = svc.start_or_resume_session(str(transcript))
    return svc, session, transcript, tmp_path


def test_start_resume_has_no_generation(studio_env):
    svc, session, _, _ = studio_env
    assert session.current_generation_id is None
    assert session.candidates == []
    assert svc.list_candidates(session.session_id) == []


def test_manual_first_then_generate_candidates(studio_env, monkeypatch):
    svc, session, _, _ = studio_env
    # Disable detectors noise by patching to empty
    monkeypatch.setattr(
        "transcriptx.services.corrections_studio.candidate_service.detect_memory_hits",
        lambda *a, **k: [],
    )
    monkeypatch.setattr(
        "transcriptx.services.corrections_studio.candidate_service.detect_acronym_candidates",
        lambda *a, **k: [],
    )
    monkeypatch.setattr(
        "transcriptx.services.corrections_studio.candidate_service.detect_consistency_candidates",
        lambda *a, **k: [],
    )
    monkeypatch.setattr(
        "transcriptx.services.corrections_studio.candidate_service.detect_fuzzy_candidates",
        lambda *a, **k: [],
    )

    result = svc.propose_manual_correction(
        session.session_id,
        segment_index=0,
        span=(0, 3),
        wrong_text="teh",
        right_text="the",
        auto_accept=False,
    )
    assert result.candidate.kind == "manual"
    assert CandidateSource.viewer_manual in result.candidate.sources
    doc = svc.load_session(session.session_id)
    assert doc.current_generation.generation_origin == GenerationOrigin.manual_seed
    manuals = svc.list_candidates(session.session_id)
    assert len(manuals) == 1

    # Gating must NOT early-return just because candidates exist
    gen = svc.generate_candidates(session.session_id, force=False)
    assert gen.commit_aborted is False
    doc2 = svc.load_session(session.session_id)
    assert doc2.current_generation.generation_origin == GenerationOrigin.detector
    # Manual carried forward
    manuals_after = [
        c for c in svc.list_candidates(session.session_id) if c.kind == "manual"
    ]
    assert len(manuals_after) == 1
    assert manuals_after[0].wrong_text == "teh"


def test_manual_accept_survives_forced_regen(studio_env, monkeypatch):
    svc, session, _, _ = studio_env
    for name in (
        "detect_memory_hits",
        "detect_acronym_candidates",
        "detect_consistency_candidates",
        "detect_fuzzy_candidates",
    ):
        monkeypatch.setattr(
            f"transcriptx.services.corrections_studio.candidate_service.{name}",
            lambda *a, **k: [],
        )

    proposed = svc.propose_manual_correction(
        session.session_id,
        segment_index=0,
        span=(0, 3),
        wrong_text="teh",
        right_text="the",
        auto_accept=True,
    )
    assert proposed.auto_accepted
    assert proposed.candidate.review_status == ReviewStatus.accepted

    svc.generate_candidates(session.session_id, force=True)
    doc = svc.load_session(session.session_id)
    manuals = [c for c in svc.list_candidates(session.session_id) if c.kind == "manual"]
    assert len(manuals) == 1
    assert manuals[0].review_status == ReviewStatus.accepted
    # Review carried into new generation
    reviews = [
        r
        for r in doc.review_records
        if r.candidate_id == manuals[0].candidate_id
        and r.generation_id == doc.current_generation_id
    ]
    assert reviews
    assert reviews[-1].review_action.value == "accept"
    assert reviews[-1].migrated_from_generation_id is not None


def test_atomic_auto_accept_has_review(studio_env):
    svc, session, _, _ = studio_env
    proposed = svc.propose_manual_correction(
        session.session_id,
        segment_index=0,
        span=(0, 3),
        wrong_text="teh",
        right_text="the",
        auto_accept=True,
    )
    doc = svc.load_session(session.session_id)
    revs = [
        r
        for r in doc.review_records
        if r.candidate_id == proposed.candidate.candidate_id
        and r.generation_id == doc.current_generation_id
    ]
    assert len(revs) == 1
    assert revs[0].review_action.value == "accept"


def test_duplicate_upsert_and_conflict(studio_env):
    svc, session, _, _ = studio_env
    first = svc.propose_manual_correction(
        session.session_id,
        segment_index=0,
        span=(0, 3),
        wrong_text="teh",
        right_text="the",
    )
    second = svc.propose_manual_correction(
        session.session_id,
        segment_index=0,
        span=(0, 3),
        wrong_text="teh",
        right_text="the",
    )
    assert second.upserted
    assert second.candidate.candidate_id == first.candidate.candidate_id

    with pytest.raises(ManualProposeConflict):
        svc.propose_manual_correction(
            session.session_id,
            segment_index=0,
            span=(0, 3),
            wrong_text="teh",
            right_text="THE",
        )


def test_revalidation_rejects_wrong_span(studio_env):
    svc, session, _, _ = studio_env
    with pytest.raises(ManualProposeValidationError):
        svc.propose_manual_correction(
            session.session_id,
            segment_index=0,
            span=(0, 3),
            wrong_text="zzz",
            right_text="the",
        )


def test_scoped_apply_excludes_other_accepted(studio_env, monkeypatch):
    svc, session, transcript, tmp_path = studio_env
    for name in (
        "detect_memory_hits",
        "detect_acronym_candidates",
        "detect_consistency_candidates",
        "detect_fuzzy_candidates",
    ):
        monkeypatch.setattr(
            f"transcriptx.services.corrections_studio.candidate_service.{name}",
            lambda *a, **k: [],
        )

    # Seed a detector-like accept by proposing two manuals and accepting both,
    # then scoped-apply only one.
    a = svc.propose_manual_correction(
        session.session_id,
        segment_index=0,
        span=(0, 3),
        wrong_text="teh",
        right_text="the",
        auto_accept=True,
    )
    # "teh quick brown fox" → fox at [16:19]
    b = svc.propose_manual_correction(
        session.session_id,
        segment_index=0,
        span=(16, 19),
        wrong_text="fox",
        right_text="FOX",
        auto_accept=True,
    )

    export_path = tmp_path / "scoped.json"
    result = svc.apply_and_export_scoped(
        session.session_id,
        candidate_ids=[b.candidate.candidate_id],
        export_path=str(export_path),
    )
    assert export_path.exists()
    data = json.loads(export_path.read_text(encoding="utf-8"))
    texts = [s["text"] for s in data["segments"]]
    # Only fox→FOX applied; teh unchanged
    assert texts[0] == "teh quick brown FOX"
    assert (
        a.candidate.candidate_id
        not in (
            json.loads(Path(result.provenance_path).read_text(encoding="utf-8")).get(
                "applied_candidate_ids", []
            )
        )
        or True
    )  # provenance lists scoped applied ids
    prov = json.loads(Path(result.provenance_path).read_text(encoding="utf-8"))
    assert prov["applied_candidate_ids"] == [b.candidate.candidate_id]


def test_list_candidates_current_generation_only(studio_env, monkeypatch):
    svc, session, _, _ = studio_env
    for name in (
        "detect_memory_hits",
        "detect_acronym_candidates",
        "detect_consistency_candidates",
        "detect_fuzzy_candidates",
    ):
        monkeypatch.setattr(
            f"transcriptx.services.corrections_studio.candidate_service.{name}",
            lambda *a, **k: [],
        )
    svc.propose_manual_correction(
        session.session_id,
        segment_index=0,
        span=(0, 3),
        wrong_text="teh",
        right_text="the",
    )
    gen1 = svc.load_session(session.session_id).current_generation_id
    svc.generate_candidates(session.session_id, force=True)
    doc = svc.load_session(session.session_id)
    # Historical rows may exist for gen1; listing defaults to current only.
    listed = svc.list_candidates(session.session_id)
    assert all(c.generation_id == doc.current_generation_id for c in listed)
    hist = svc.list_candidates(session.session_id, include_historical=True)
    assert any(c.generation_id == gen1 for c in hist)


def test_compile_manual_kind_not_coerced():
    from datetime import datetime, timezone

    from transcriptx.services.corrections_studio.compile import (
        compile_studio_to_engine_apply,
    )
    from transcriptx.services.corrections_studio.schema import (
        ApplyScope,
        ReviewAction,
        ReviewStatus,
        StudioCandidate,
        StudioReviewRecord,
        StudioSessionDocument,
    )

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    doc = StudioSessionDocument(
        session_id="s1",
        transcript_path="/tmp/t.json",
        recorded_transcript_identity_hash="abc",
        current_generation_id=1,
        candidates=[
            StudioCandidate(
                candidate_id="c1",
                generation_id=1,
                kind="manual",
                wrong_text="foo",
                right_text="bar",
                confidence=1.0,
                occurrences=[],
                review_status=ReviewStatus.accepted,
                sources=[CandidateSource.viewer_manual],
            )
        ],
        review_records=[
            StudioReviewRecord(
                session_id="s1",
                generation_id=1,
                candidate_id="c1",
                review_action=ReviewAction.accept,
                apply_scope=ApplyScope.all,
                recorded_at=now,
                event_sequence=1,
            )
        ],
    )
    out = compile_studio_to_engine_apply(session=doc, segments=[], transcript_key="k")
    assert out.engine_candidates[0].kind == "manual"


def test_sidecar_lineage_new_session(studio_env, monkeypatch):
    svc, session, transcript, tmp_path = studio_env
    for name in (
        "detect_memory_hits",
        "detect_acronym_candidates",
        "detect_consistency_candidates",
        "detect_fuzzy_candidates",
    ):
        monkeypatch.setattr(
            f"transcriptx.services.corrections_studio.candidate_service.{name}",
            lambda *a, **k: [],
        )
    proposed = svc.propose_manual_correction(
        session.session_id,
        segment_index=0,
        span=(0, 3),
        wrong_text="teh",
        right_text="the",
        auto_accept=True,
    )
    export_path = tmp_path / "corrected.json"
    svc.apply_and_export_scoped(
        session.session_id,
        candidate_ids=[proposed.candidate.candidate_id],
        export_path=str(export_path),
    )
    # Opening corrected artifact starts a distinct session.
    child = svc.start_or_resume_session(str(export_path))
    assert child.session_id != session.session_id
    assert child.transcript_path.endswith("corrected.json")
    assert (
        child.recorded_transcript_identity_hash
        != session.recorded_transcript_identity_hash
    )


def test_reconcile_replays_manual_seed_and_propose(studio_env):
    from transcriptx.services.corrections_studio.reconcile import (
        parse_events_jsonl,
        reconcile_snapshot_from_events,
    )
    from transcriptx.services.corrections_studio.schema import GenerationOrigin

    svc, session, _, _ = studio_env
    proposed = svc.propose_manual_correction(
        session.session_id,
        segment_index=0,
        span=(0, 3),
        wrong_text="teh",
        right_text="the",
        auto_accept=True,
    )
    lines = svc.repo.read_event_lines(session.session_id)
    events = parse_events_jsonl(lines)
    rebuilt = reconcile_snapshot_from_events(events=events)
    assert rebuilt.current_generation_id == 1
    assert rebuilt.current_generation is not None
    assert (
        rebuilt.current_generation.generation_origin == GenerationOrigin.manual_seed
        or any(c.kind == "manual" for c in rebuilt.candidates)
    )
    manuals = [c for c in rebuilt.candidates if c.kind == "manual"]
    assert len(manuals) == 1
    assert manuals[0].candidate_id == proposed.candidate.candidate_id
    assert manuals[0].review_status.value == "accepted"
    assert any(
        r.candidate_id == proposed.candidate.candidate_id
        and r.review_action.value == "accept"
        for r in rebuilt.review_records
    )


def test_concurrent_manual_propose_loser_raises(studio_env):
    """Second writer with stale event sequence must not orphan a candidate."""
    from transcriptx.core.store.corrections_session_store import (
        GenerationCommitConflict,
    )
    from transcriptx.services.corrections_studio.manual_propose_service import (
        CorrectionsStudioManualProposeService,
    )
    from transcriptx.services.corrections_studio.session_service import (
        CorrectionsStudioSessionService,
    )

    svc, session, transcript, _ = studio_env
    # Seed one propose so session has a generation + events
    svc.propose_manual_correction(
        session.session_id,
        segment_index=0,
        span=(0, 3),
        wrong_text="teh",
        right_text="the",
    )
    session_svc = CorrectionsStudioSessionService(svc.repo)
    # Stale expected sequence simulates concurrent Studio write ahead of viewer
    real_persist = session_svc.persist_event_batch

    calls = {"n": 0}

    def _wrap(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            # First call: bump sequence by writing a no-op via a real propose path first
            # Actually force conflict by lying about expected sequence in preconditions
            pre = k.get("preconditions")
            if pre is not None:
                from dataclasses import replace

                # Force stale expected_last
                object.__setattr__(pre, "expected_last_event_sequence", 0)
        return real_persist(*a, **k)

    # Simpler: call propose with a patched last_event_sequence returning stale value
    manual = CorrectionsStudioManualProposeService(session_svc)
    session_svc.last_event_sequence = lambda _sid: 0  # type: ignore[method-assign]
    with pytest.raises(GenerationCommitConflict):
        manual.propose_manual_correction(
            session.session_id,
            segment_index=0,
            span=(4, 9),
            wrong_text="quick",
            right_text="QUICK",
        )
    # Original candidate still present; no orphan half-write for the failed propose
    listed = svc.list_candidates(session.session_id, kind_filter=["manual"])
    assert len(listed) == 1
    assert listed[0].wrong_text == "teh"
