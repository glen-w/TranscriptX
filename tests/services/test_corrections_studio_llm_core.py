"""LLM contract, grounding, merge, migration, budgets, compile re-ground."""

from __future__ import annotations

from typing import Any, Dict

import pytest

from transcriptx.core.corrections.models import Candidate as EngineCandidate
from transcriptx.core.corrections.models import Occurrence
from transcriptx.core.llm.errors import LLMResponseError
from transcriptx.services.corrections_studio.compile import (
    compile_studio_to_engine_apply,
)
from transcriptx.services.corrections_studio.llm.budgets import BudgetTracker
from transcriptx.services.corrections_studio.llm.chunking import build_segment_chunks
from transcriptx.services.corrections_studio.llm.contract import parse_discovery_json
from transcriptx.services.corrections_studio.llm.grounding import (
    ground_discovery_candidates,
)
from transcriptx.services.corrections_studio.llm.merge import (
    annotate_engine_candidates,
    cross_kind_merge,
)
from transcriptx.services.corrections_studio.llm.review_migration import (
    build_review_migration_plan,
)
from transcriptx.services.corrections_studio.schema import (
    ApplyScope,
    CandidateSource,
    ReviewAction,
    ReviewStatus,
    StudioCandidate,
    StudioOccurrence,
    StudioReviewRecord,
    StudioSessionDocument,
)
from transcriptx.services.corrections_studio.semantic_identity import (
    compute_semantic_identity_key,
)


def _seg(i: int, text: str) -> Dict[str, Any]:
    return {
        "id": f"s{i}",
        "text": text,
        "speaker": "A",
        "start": float(i),
        "end": float(i) + 1,
    }


@pytest.mark.unit
def test_parse_discovery_valid_and_reject_extra() -> None:
    raw = '{"candidates":[{"source_text":"Foo","replacement_text":"Bar","segment_ref":0,"rationale":"x","certainty_label":"confident","evidence_signals":["model_suggestion"]}]}'
    got = parse_discovery_json(raw)
    assert len(got) == 1
    with pytest.raises(LLMResponseError):
        parse_discovery_json(
            '{"candidates":[{"source_text":"a","replacement_text":"b","segment_ref":0,"extra":1}]}'
        )


@pytest.mark.unit
def test_grounding_rejects_hallucinated_and_accepts_exact() -> None:
    segs = [_seg(0, "Hello Wren twenty one today"), _seg(1, "Wren twenty one again")]
    raw = [
        {
            "source_text": "Wren twenty one",
            "replacement_text": "REN21",
            "segment_ref": 0,
        },
        {
            "source_text": "not-in-transcript",
            "replacement_text": "X",
            "segment_ref": 0,
        },
        {
            "source_text": "Wren twenty one",
            "replacement_text": "Wren twenty one",
            "segment_ref": 0,
        },
    ]
    res = ground_discovery_candidates(
        raw, segments=segs, transcript_key="tk", max_per_chunk=10
    )
    assert len(res.accepted) == 1
    assert res.rejected >= 2
    assert len(res.accepted[0].occurrences) >= 2  # expansion


@pytest.mark.unit
def test_chunking_overlap_and_cap() -> None:
    segs = [_seg(i, f"t{i}") for i in range(100)]
    chunks = build_segment_chunks(
        segs, chunk_max_segments=40, chunk_overlap_segments=4, max_chunks=3
    )
    assert len(chunks) == 3
    assert chunks[0].segment_indices[0] == 0


@pytest.mark.unit
def test_cross_kind_merge_memory_wins() -> None:
    mem = EngineCandidate(
        proposed_wrong="foo",
        proposed_right="bar",
        kind="memory_hit",
        confidence=0.9,
        occurrences=[
            Occurrence(segment_id="s0", span=(0, 3), snippet="foo", occurrence_id="k1")
        ],
    )
    llm = EngineCandidate(
        proposed_wrong="foo",
        proposed_right="bar",
        kind="ner_variant",
        confidence=0.4,
        occurrences=[
            Occurrence(segment_id="s0", span=(0, 3), snippet="foo", occurrence_id="k1")
        ],
    )
    ann = annotate_engine_candidates([mem]) + annotate_engine_candidates(
        [llm], default_source=CandidateSource.llm_discovery
    )
    merged, _ = cross_kind_merge(ann)
    assert len(merged) == 1
    assert merged[0].engine.kind == "memory_hit"
    assert CandidateSource.llm_discovery in merged[0].sources
    assert CandidateSource.detector_memory in merged[0].sources


@pytest.mark.unit
def test_review_migration_apply_all_requires_identical_occurrences() -> None:
    sem = compute_semantic_identity_key("foo", "bar")
    prior = StudioCandidate(
        candidate_id="c1",
        generation_id=1,
        kind="consistency",
        wrong_text="foo",
        right_text="bar",
        occurrences=[
            StudioOccurrence(
                segment_id="s0", stable_occurrence_key="k1", span=(0, 3), snippet="foo"
            )
        ],
        semantic_identity_key=sem,
        review_status=ReviewStatus.accepted,
    )
    review = StudioReviewRecord(
        session_id="s",
        generation_id=1,
        candidate_id="c1",
        review_action=ReviewAction.accept,
        apply_scope=ApplyScope.all,
        recorded_at="t",
        event_sequence=1,
    )
    # New occurrence appeared
    new = prior.model_copy(
        update={
            "candidate_id": "c2",
            "generation_id": 2,
            "occurrences": [
                StudioOccurrence(
                    segment_id="s0",
                    stable_occurrence_key="k1",
                    span=(0, 3),
                    snippet="foo",
                ),
                StudioOccurrence(
                    segment_id="s1",
                    stable_occurrence_key="k2",
                    span=(0, 3),
                    snippet="foo",
                ),
            ],
        }
    )
    plan = build_review_migration_plan(
        prior_candidates=[prior],
        prior_reviews=[review],
        new_candidates=[new],
        prior_generation_id=1,
        new_generation_id=2,
    )
    assert plan.summary.carried == 0
    assert plan.summary.reset >= 1

    # Identical set carries
    identical = prior.model_copy(update={"candidate_id": "c3", "generation_id": 2})
    plan2 = build_review_migration_plan(
        prior_candidates=[prior],
        prior_reviews=[review],
        new_candidates=[identical],
        prior_generation_id=1,
        new_generation_id=2,
    )
    assert plan2.summary.carried == 1
    assert plan2.reviews[0].migrated_from_generation_id == 1


@pytest.mark.unit
def test_migration_kind_change_does_not_block() -> None:
    sem = compute_semantic_identity_key("foo", "bar")
    prior = StudioCandidate(
        candidate_id="c1",
        generation_id=1,
        kind="ner_variant",
        wrong_text="foo",
        right_text="bar",
        occurrences=[
            StudioOccurrence(
                segment_id="s0", stable_occurrence_key="k1", span=(0, 3), snippet="foo"
            )
        ],
        semantic_identity_key=sem,
    )
    review = StudioReviewRecord(
        session_id="s",
        generation_id=1,
        candidate_id="c1",
        review_action=ReviewAction.reject,
        recorded_at="t",
        event_sequence=1,
    )
    new = prior.model_copy(
        update={"candidate_id": "c2", "generation_id": 2, "kind": "memory_hit"}
    )
    plan = build_review_migration_plan(
        prior_candidates=[prior],
        prior_reviews=[review],
        new_candidates=[new],
        prior_generation_id=1,
        new_generation_id=2,
    )
    assert plan.summary.carried == 1


@pytest.mark.unit
def test_compile_regrounds_and_drops_stale() -> None:
    sem = compute_semantic_identity_key("foo", "bar")
    cand = StudioCandidate(
        candidate_id="c1",
        generation_id=1,
        kind="consistency",
        wrong_text="foo",
        right_text="bar",
        occurrences=[
            StudioOccurrence(
                segment_id="s0", stable_occurrence_key="k1", span=(0, 3), snippet="foo"
            ),
            StudioOccurrence(
                segment_id="s0",
                stable_occurrence_key="k_bad",
                span=(99, 102),
                snippet="xxx",
            ),
        ],
        semantic_identity_key=sem,
    )
    review = StudioReviewRecord(
        session_id="s",
        generation_id=1,
        candidate_id="c1",
        review_action=ReviewAction.accept,
        apply_scope=ApplyScope.all,
        recorded_at="t",
        event_sequence=1,
    )
    session = StudioSessionDocument(
        session_id="s",
        transcript_path="/t.json",
        recorded_transcript_identity_hash="h",
        current_generation_id=1,
        candidates=[cand],
        review_records=[review],
    )
    segments = [{"id": "s0", "text": "foo bar", "speaker": "A"}]
    compiled = compile_studio_to_engine_apply(
        session=session, segments=segments, transcript_key="tk"
    )
    assert len(compiled.engine_candidates) == 1
    assert len(compiled.engine_candidates[0].occurrences) == 1
    assert compiled.compile_diagnostics["dropped_occurrences"] >= 1


@pytest.mark.unit
def test_budget_tracker_exhaustion() -> None:
    b = BudgetTracker.start(
        request_timeout_seconds=1.0, total_wall_clock_seconds=0.0, max_chunks=5
    )
    ok, reason = b.can_start_chunk()
    assert ok is False
    assert reason == "budget_exhausted"


@pytest.mark.unit
def test_budget_tracker_apportion_timeout_across_retries() -> None:
    b = BudgetTracker.start(
        request_timeout_seconds=120.0,
        total_wall_clock_seconds=180.0,
        max_chunks=5,
        transport_max_attempts=3,
    )
    per = b.note_chunk_started()
    assert per == pytest.approx(40.0)


@pytest.mark.unit
def test_review_migration_selected_carries_surviving_keys_only() -> None:
    sem = compute_semantic_identity_key("foo", "bar")
    prior = StudioCandidate(
        candidate_id="c1",
        generation_id=1,
        kind="consistency",
        wrong_text="foo",
        right_text="bar",
        occurrences=[
            StudioOccurrence(
                segment_id="s0", stable_occurrence_key="k1", span=(0, 3), snippet="foo"
            ),
            StudioOccurrence(
                segment_id="s1", stable_occurrence_key="k2", span=(0, 3), snippet="foo"
            ),
        ],
        semantic_identity_key=sem,
    )
    review = StudioReviewRecord(
        session_id="s",
        generation_id=1,
        candidate_id="c1",
        review_action=ReviewAction.accept,
        apply_scope=ApplyScope.selected,
        selected_occurrence_keys=["k1", "k2"],
        recorded_at="t",
        event_sequence=1,
    )
    new = prior.model_copy(
        update={
            "candidate_id": "c2",
            "generation_id": 2,
            "occurrences": [
                StudioOccurrence(
                    segment_id="s0",
                    stable_occurrence_key="k1",
                    span=(0, 3),
                    snippet="foo",
                )
            ],
        }
    )
    plan = build_review_migration_plan(
        prior_candidates=[prior],
        prior_reviews=[review],
        new_candidates=[new],
        prior_generation_id=1,
        new_generation_id=2,
    )
    assert plan.summary.carried == 1
    assert plan.reviews[0].selected_occurrence_keys == ["k1"]
    assert plan.reviews[0].apply_scope == ApplyScope.selected


@pytest.mark.unit
def test_review_migration_resets_invalid_edited_target() -> None:
    sem = compute_semantic_identity_key("foo", "bar")
    prior = StudioCandidate(
        candidate_id="c1",
        generation_id=1,
        kind="consistency",
        wrong_text="foo",
        right_text="bar",
        occurrences=[
            StudioOccurrence(
                segment_id="s0", stable_occurrence_key="k1", span=(0, 3), snippet="foo"
            )
        ],
        semantic_identity_key=sem,
    )
    review = StudioReviewRecord(
        session_id="s",
        generation_id=1,
        candidate_id="c1",
        review_action=ReviewAction.accept,
        apply_scope=ApplyScope.all,
        review_target_text="foo",
        recorded_at="t",
        event_sequence=1,
    )
    new = prior.model_copy(update={"candidate_id": "c2", "generation_id": 2})
    plan = build_review_migration_plan(
        prior_candidates=[prior],
        prior_reviews=[review],
        new_candidates=[new],
        prior_generation_id=1,
        new_generation_id=2,
    )
    assert plan.summary.carried == 0
    assert plan.summary.reset >= 1


@pytest.mark.unit
def test_review_migration_learn_requires_resolvable_rule() -> None:
    from transcriptx.services.corrections_studio.schema import StudioRule

    sem = compute_semantic_identity_key("foo", "bar")
    prior = StudioCandidate(
        candidate_id="c1",
        generation_id=1,
        kind="consistency",
        wrong_text="foo",
        right_text="bar",
        occurrences=[
            StudioOccurrence(
                segment_id="s0", stable_occurrence_key="k1", span=(0, 3), snippet="foo"
            )
        ],
        semantic_identity_key=sem,
    )
    review = StudioReviewRecord(
        session_id="s",
        generation_id=1,
        candidate_id="c1",
        review_action=ReviewAction.learn,
        apply_scope=ApplyScope.all,
        learn_rule_id="missing_rule",
        recorded_at="t",
        event_sequence=1,
    )
    new = prior.model_copy(update={"candidate_id": "c2", "generation_id": 2})
    plan = build_review_migration_plan(
        prior_candidates=[prior],
        prior_reviews=[review],
        new_candidates=[new],
        prior_generation_id=1,
        new_generation_id=2,
        rules_by_id={},
    )
    assert plan.summary.carried == 0

    rule = StudioRule(
        rule_id="missing_rule",
        rule_type="phrase",
        wrong_variants=["foo"],
        replacement_text="bar",
    )
    plan2 = build_review_migration_plan(
        prior_candidates=[prior],
        prior_reviews=[review],
        new_candidates=[new],
        prior_generation_id=1,
        new_generation_id=2,
        rules_by_id={"missing_rule": rule},
    )
    assert plan2.summary.carried == 1


@pytest.mark.unit
def test_compile_drops_missing_segment_and_stale_text() -> None:
    cand = StudioCandidate(
        candidate_id="c1",
        generation_id=1,
        kind="consistency",
        wrong_text="foo",
        right_text="bar",
        occurrences=[
            StudioOccurrence(
                segment_id="missing",
                stable_occurrence_key="k_miss",
                span=(0, 3),
                snippet="foo",
            ),
            StudioOccurrence(
                segment_id="s0",
                stable_occurrence_key="k_stale",
                span=(0, 3),
                snippet="zzz",
            ),
        ],
        semantic_identity_key=compute_semantic_identity_key("foo", "bar"),
    )
    review = StudioReviewRecord(
        session_id="s",
        generation_id=1,
        candidate_id="c1",
        review_action=ReviewAction.accept,
        apply_scope=ApplyScope.all,
        recorded_at="t",
        event_sequence=1,
    )
    session = StudioSessionDocument(
        session_id="s",
        transcript_path="/t.json",
        recorded_transcript_identity_hash="h",
        current_generation_id=1,
        candidates=[cand],
        review_records=[review],
    )
    # Live text no longer matches wrong_text at span
    segments = [{"id": "s0", "text": "zzz bar", "speaker": "A"}]
    compiled = compile_studio_to_engine_apply(
        session=session, segments=segments, transcript_key="tk"
    )
    assert compiled.engine_candidates == []
    assert compiled.compile_diagnostics["dropped_candidates"] >= 1


@pytest.mark.unit
def test_compile_accepts_llm_discovery_candidate() -> None:
    cand = StudioCandidate(
        candidate_id="c1",
        generation_id=1,
        kind="ner_variant",
        wrong_text="foo",
        right_text="bar",
        sources=[CandidateSource.llm_discovery],
        occurrences=[
            StudioOccurrence(
                segment_id="s0", stable_occurrence_key="k1", span=(0, 3), snippet="foo"
            )
        ],
        semantic_identity_key=compute_semantic_identity_key("foo", "bar"),
    )
    review = StudioReviewRecord(
        session_id="s",
        generation_id=1,
        candidate_id="c1",
        review_action=ReviewAction.accept,
        apply_scope=ApplyScope.all,
        recorded_at="t",
        event_sequence=1,
    )
    session = StudioSessionDocument(
        session_id="s",
        transcript_path="/t.json",
        recorded_transcript_identity_hash="h",
        current_generation_id=1,
        candidates=[cand],
        review_records=[review],
    )
    compiled = compile_studio_to_engine_apply(
        session=session,
        segments=[{"id": "s0", "text": "foo bar", "speaker": "A"}],
        transcript_key="tk",
    )
    assert len(compiled.engine_candidates) == 1
    assert compiled.engine_candidates[0].kind == "ner_variant"


@pytest.mark.unit
def test_merge_evidence_ranking_does_not_mutate_rule_confidence() -> None:
    from transcriptx.core.corrections.models import CorrectionRule

    rule = CorrectionRule(
        id="r1",
        type="phrase",
        wrong=["foo"],
        right="bar",
        scope="global",
        confidence=0.91,
    )
    mem = EngineCandidate(
        proposed_wrong="foo",
        proposed_right="bar",
        kind="memory_hit",
        confidence=0.5,
        rule_id="r1",
        occurrences=[
            Occurrence(segment_id="s0", span=(0, 3), snippet="foo", occurrence_id="k1")
        ],
    )
    llm = EngineCandidate(
        proposed_wrong="foo",
        proposed_right="bar",
        kind="ner_variant",
        confidence=0.99,
        occurrences=[
            Occurrence(segment_id="s0", span=(0, 3), snippet="foo", occurrence_id="k1")
        ],
    )
    ann = annotate_engine_candidates([mem]) + annotate_engine_candidates(
        [llm], default_source=CandidateSource.llm_discovery
    )
    cross_kind_merge(ann, rules_by_id={"r1": rule})
    assert rule.confidence == 0.91


@pytest.mark.unit
def test_grounding_casefold_multiword() -> None:
    segs = [_seg(0, "Hello Wren Twenty One today")]
    raw = [
        {
            "source_text": "wren twenty one",
            "replacement_text": "REN21",
            "segment_ref": 0,
        }
    ]
    res = ground_discovery_candidates(
        raw, segments=segs, transcript_key="tk", max_per_chunk=10
    )
    assert len(res.accepted) == 1


@pytest.mark.unit
def test_run_llm_discovery_disabled_makes_zero_client_calls(monkeypatch) -> None:
    from unittest.mock import MagicMock

    from transcriptx.services.corrections_studio.llm import discovery as disc

    built = {"n": 0}

    def _boom(**kwargs):
        built["n"] += 1
        raise AssertionError("client should not be built")

    monkeypatch.setattr(disc, "build_ollama_analysis_client", _boom)
    result = disc.run_llm_discovery(
        segments=[_seg(0, "hi")],
        transcript_key="tk",
        llm_cfg=MagicMock(enabled=False, provider="ollama"),
        corrections_llm=MagicMock(enabled=False),
        speaker_names=[],
        memory_pairs=[],
        known_acronyms=[],
        known_org_phrases={},
    )
    assert result.diagnostics.outcome == "skipped"
    assert result.diagnostics.attempted is False
    assert built["n"] == 0
    assert result.candidates == []


@pytest.mark.unit
def test_run_llm_discovery_budget_exhaustion_retains_prior_chunks(monkeypatch) -> None:
    from unittest.mock import MagicMock

    from transcriptx.core.analysis.llm_support.runtime import LLMRuntime
    from transcriptx.services.corrections_studio.llm import budgets as budgets_mod
    from transcriptx.services.corrections_studio.llm import discovery as disc

    segs = [_seg(i, f"Wren twenty one segment {i}") for i in range(5)]
    calls = {"n": 0}
    clock = {"t": 0.0}

    class FakeClient:
        def is_available(self):
            return True

        def generate(self, **kwargs):
            calls["n"] += 1
            # Exhaust wall clock before the next chunk is scheduled.
            clock["t"] = 999.0
            return (
                '{"candidates":[{"source_text":"Wren twenty one",'
                '"replacement_text":"REN21","segment_ref":0,'
                '"rationale":"x","certainty_label":"tentative",'
                '"evidence_signals":["model_suggestion"]}]}'
            )

    monkeypatch.setattr(budgets_mod.time, "monotonic", lambda: clock["t"])
    monkeypatch.setattr(disc, "build_ollama_analysis_client", lambda **kw: FakeClient())
    monkeypatch.setattr(
        disc,
        "resolve_llm_runtime",
        lambda **kw: LLMRuntime(
            effort="low",
            profile_name="low",
            model="m",
            max_input_chars=50_000,
            request_timeout=30.0,
            max_output_tokens=512,
        ),
    )

    corrections_llm = MagicMock(
        enabled=True,
        effort="low",
        request_timeout_seconds=30.0,
        total_wall_clock_seconds=10.0,
        max_chunks=25,
        chunk_max_segments=1,
        chunk_overlap_segments=0,
        max_candidates_per_chunk=5,
        max_candidates_per_transcript=80,
        continue_on_failure=True,
        assess_deterministic=False,
    )
    llm_cfg = MagicMock(
        enabled=True,
        provider="ollama",
        base_url="http://127.0.0.1:11434",
        default_temperature=0.0,
        model="m",
    )
    result = disc.run_llm_discovery(
        segments=segs,
        transcript_key="tk",
        llm_cfg=llm_cfg,
        corrections_llm=corrections_llm,
        speaker_names=[],
        memory_pairs=[],
        known_acronyms=[],
        known_org_phrases={},
    )
    assert calls["n"] == 1
    assert result.diagnostics.budget_reason == "budget_exhausted"
    assert result.diagnostics.outcome == "partial"
    assert len(result.candidates) >= 1


@pytest.mark.unit
def test_run_llm_discovery_setup_failure_degrades(monkeypatch) -> None:
    from unittest.mock import MagicMock

    from transcriptx.services.corrections_studio.llm import discovery as disc

    monkeypatch.setattr(
        disc,
        "resolve_llm_runtime",
        lambda **kw: (_ for _ in ()).throw(ValueError("bad effort")),
    )
    result = disc.run_llm_discovery(
        segments=[_seg(0, "hi")],
        transcript_key="tk",
        llm_cfg=MagicMock(
            enabled=True, provider="ollama", base_url="http://127.0.0.1:11434"
        ),
        corrections_llm=MagicMock(
            enabled=True, effort="nope", continue_on_failure=True
        ),
        speaker_names=[],
        memory_pairs=[],
        known_acronyms=[],
        known_org_phrases={},
    )
    assert result.diagnostics.outcome == "failed"
    assert result.candidates == []
