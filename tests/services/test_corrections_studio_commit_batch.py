"""Unit tests for Corrections Studio commit_generation_batch (0.3.9 split)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from transcriptx.services.corrections_studio.candidate_commit import (
    commit_generation_batch,
)
from transcriptx.services.corrections_studio.schema import (
    ApplyScope,
    CandidateGenerationDiagnostics,
    DetectorCountsByKind,
    FuzzySkippedReason,
    GenerationManifest,
    ReviewAction,
    ReviewStatus,
    StudioCandidate,
    StudioSessionDocument,
)


def _manifest() -> GenerationManifest:
    return GenerationManifest(
        transcript_identity_hash="h",
        corrections_config_fingerprint="c",
        detector_version="3",
        memory_rule_fingerprint="m",
        speaker_map_fingerprint="",
        studio_session_rules_fingerprint="r",
    )


def _diag() -> CandidateGenerationDiagnostics:
    zeros = DetectorCountsByKind()
    return CandidateGenerationDiagnostics(
        pre_dedupe=zeros,
        total_pre_dedupe=0,
        post_dedupe_counts_by_kind=zeros,
        total_after_dedupe=0,
        fuzzy_enabled=False,
        fuzzy_skipped_reason=FuzzySkippedReason.disabled,
    )


@pytest.mark.unit
def test_commit_generation_batch_applies_migrated_review_statuses() -> None:
    prior = StudioSessionDocument(
        session_id="s1",
        transcript_path="/tmp/t.json",
        recorded_transcript_identity_hash="h",
        current_generation_id=1,
        candidates=[],
        review_records=[],
        created_at="2026-01-01T00:00:00Z",
    )
    cands = [
        StudioCandidate(
            candidate_id="c_accept",
            generation_id=2,
            kind="acronym",
            wrong_text="a",
            right_text="A",
            confidence=0.9,
            occurrences=[],
            review_status=ReviewStatus.pending,
        ),
        StudioCandidate(
            candidate_id="c_reject",
            generation_id=2,
            kind="acronym",
            wrong_text="b",
            right_text="B",
            confidence=0.9,
            occurrences=[],
            review_status=ReviewStatus.pending,
        ),
        StudioCandidate(
            candidate_id="c_other",
            generation_id=2,
            kind="acronym",
            wrong_text="c",
            right_text="C",
            confidence=0.9,
            occurrences=[],
            review_status=ReviewStatus.pending,
        ),
    ]
    migrations = [
        SimpleNamespace(
            candidate_id="c_accept",
            review_action=ReviewAction.accept,
            apply_scope=ApplyScope.all,
            selected_occurrence_keys=[],
            learn_intent=None,
            learn_rule_id=None,
            review_target_text="",
            migrated_from_generation_id=1,
            model_dump=lambda mode="json": {"candidate_id": "c_accept"},
        ),
        SimpleNamespace(
            candidate_id="c_reject",
            review_action=ReviewAction.reject,
            apply_scope=ApplyScope.all,
            selected_occurrence_keys=[],
            learn_intent=None,
            learn_rule_id=None,
            review_target_text="",
            migrated_from_generation_id=1,
            model_dump=lambda mode="json": {"candidate_id": "c_reject"},
        ),
        SimpleNamespace(
            candidate_id="c_other",
            review_action=ReviewAction.skip,
            apply_scope=ApplyScope.all,
            selected_occurrence_keys=[],
            learn_intent=None,
            learn_rule_id=None,
            review_target_text="",
            migrated_from_generation_id=1,
            model_dump=lambda mode="json": {"candidate_id": "c_other"},
        ),
    ]
    session_svc = MagicMock()
    out = commit_generation_batch(
        session_service=session_svc,
        session_id="s1",
        transcript_path="/tmp/t.json",
        prior_doc=prior,
        new_gen=2,
        manifest=_manifest(),
        mh="hash",
        diagnostics=_diag(),
        studio_candidates=cands,
        migration_payloads=migrations,
        expected_last_event_sequence=0,
        expected_generation_id=1,
        expected_transcript_identity_hash="h",
        expected_rules_fp="r",
    )
    by_id = {c.candidate_id: c.review_status for c in out}
    assert by_id["c_accept"] == ReviewStatus.accepted
    assert by_id["c_reject"] == ReviewStatus.rejected
    assert by_id["c_other"] == ReviewStatus.pending
    session_svc.persist_event_batch.assert_called_once()
    _doc, events = (
        session_svc.persist_event_batch.call_args.args[1],
        session_svc.persist_event_batch.call_args.args[2],
    )
    assert _doc.current_generation_id == 2
    # candidates_generated + 3 migrated review_recorded
    assert len(events) == 4
    assert events[0].event_type == "candidates_generated"
    assert sum(1 for e in events if e.event_type == "review_recorded") == 3
