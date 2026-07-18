"""Tests for interactions polarity, equity, charts, and group semantics gate."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from transcriptx.core.analysis.aggregation.interactions import (
    aggregate_interactions_group,
)
from transcriptx.core.analysis.interactions.analyzer import SpeakerInteractionAnalyzer
from transcriptx.core.analysis.interactions.equity import (
    ABSTAIN_NO_INTERRUPTIONS,
    ABSTAIN_ZERO_TOTAL_DURATION,
    compute_equity,
    empty_equity,
    nearest_rank_p90,
)
from transcriptx.core.analysis.interactions.events import InteractionEvent
from transcriptx.core.analysis.interactions.roles import (
    INTERACTIONS_SEMANTICS_VERSION,
    interruption_balance_index,
    resolve_interaction_roles,
)
from transcriptx.core.analysis.interactions.serialize import (
    serialize_equity,
    serialize_interactions_summary,
)
from transcriptx.core.analysis.interactions.visualization import (
    create_equity_floor_chart,
    create_equity_summary_chart,
)
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap
from transcriptx.core.utils.segment_duration import (
    SpeakerDurationResult,
    compute_eligible_speaker_durations,
)
from transcriptx.web.summary_extractors.interactions import (
    extract_interactions_summary,
)


def _event(
    *,
    itype: str,
    speaker_a: str,
    speaker_b: str,
    gap: float = 0.2,
) -> InteractionEvent:
    return InteractionEvent(
        timestamp=1.0,
        speaker_a=speaker_a,
        speaker_b=speaker_b,
        interaction_type=itype,
        speaker_a_text="a",
        speaker_b_text="b",
        gap_before=gap,
        overlap=0.0,
        speaker_a_start=0.0,
        speaker_a_end=1.0,
        speaker_b_start=1.2,
        speaker_b_end=2.0,
    )


def test_role_resolver_directions() -> None:
    ov = _event(itype="interruption_overlap", speaker_a="Alice", speaker_b="Bob")
    roles = resolve_interaction_roles(ov)
    assert roles is not None
    assert roles.actor == "Bob"
    assert roles.target == "Alice"
    assert roles.matrix_key == "interruptions"

    resp = _event(itype="response", speaker_a="Alice", speaker_b="Carol")
    roles_r = resolve_interaction_roles(resp)
    assert roles_r is not None
    assert roles_r.actor == "Carol"
    assert roles_r.target == "Alice"


def test_analyze_polarity_and_matrix_and_dominance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "transcriptx.core.analysis.interactions.analyzer.notify_user",
        lambda *a, **k: None,
    )
    analyzer = SpeakerInteractionAnalyzer(
        min_segment_length=0.1,
        overlap_threshold=0.5,
        response_threshold=2.0,
        include_overlaps=True,
        include_responses=True,
    )
    # Bob overlaps Alice → Bob interrupts Alice
    events = [
        _event(itype="interruption_overlap", speaker_a="Alice", speaker_b="Bob"),
        _event(itype="response", speaker_a="Alice", speaker_b="Bob", gap=0.3),
    ]
    result = analyzer.analyze_interactions(events)
    assert result["semantics_version"] == INTERACTIONS_SEMANTICS_VERSION
    assert result["interruption_initiated"]["Bob"] == 1
    assert result["interruption_received"]["Alice"] == 1
    assert "Alice" not in result["interruption_initiated"]
    assert result["responses_initiated"]["Bob"] == 1
    assert result["responses_received"]["Alice"] == 1
    assert result["interaction_matrix"]["Bob"]["Alice"]["interruptions"] == 1
    assert result["interaction_matrix"]["Bob"]["Alice"]["responses"] == 1
    # Bob initiated 2, received 0 → dominance +1
    assert result["dominance_scores"]["Bob"] == pytest.approx(1.0)
    assert result["dominance_scores"]["Alice"] == pytest.approx(-1.0)


def test_unknown_interaction_type_skipped() -> None:
    analyzer = SpeakerInteractionAnalyzer()
    events = [_event(itype="mystery", speaker_a="Alice", speaker_b="Bob")]
    result = analyzer.analyze_interactions(events)
    assert result["interruption_initiated"] == {}
    assert result["ignored_unknown_interaction_types"]["mystery"] == 1


def test_nearest_rank_p90() -> None:
    # n=10 → ceil(9)-1 = 8 → 9th value (0-based index 8)
    values = [float(i) for i in range(1, 11)]
    assert nearest_rank_p90(values) == 9.0
    assert nearest_rank_p90([5.0]) == 5.0


def test_floor_equal_and_monopolised() -> None:
    equal = SpeakerDurationResult(
        durations={"Alice": 10.0, "Bob": 10.0},
        eligible_speakers=("Alice", "Bob"),
        speaker_segments={},
        speaker_key_map={},
        total_valid_duration=20.0,
    )
    eq = compute_equity(
        duration_result=equal,
        interruption_initiated={},
        interruption_received={},
        interactions=[],
    )
    assert eq["floor_equity_index"] == pytest.approx(1.0)
    assert eq["floor_share"]["Alice"] == pytest.approx(0.5)

    mono = SpeakerDurationResult(
        durations={"Alice": 20.0, "Bob": 0.0},
        eligible_speakers=("Alice", "Bob"),
        speaker_segments={},
        speaker_key_map={},
        total_valid_duration=20.0,
    )
    eq2 = compute_equity(
        duration_result=mono,
        interruption_initiated={},
        interruption_received={},
        interactions=[],
    )
    assert eq2["floor_equity_index"] == pytest.approx(0.0)
    assert "Bob" in eq2["floor_share"]
    assert eq2["floor_share"]["Bob"] == 0.0


def test_floor_zero_duration_abstains() -> None:
    zero = SpeakerDurationResult(
        durations={"Alice": 0.0, "Bob": 0.0},
        eligible_speakers=("Alice", "Bob"),
        speaker_segments={},
        speaker_key_map={},
        total_valid_duration=0.0,
    )
    eq = compute_equity(
        duration_result=zero,
        interruption_initiated={},
        interruption_received={},
        interactions=[],
    )
    assert eq["floor_equity_index"] is None
    assert eq["floor_share"] == {}
    assert any(a["reason"] == ABSTAIN_ZERO_TOTAL_DURATION for a in eq["abstentions"])


def test_asymmetry_one_way_and_balance_presentation() -> None:
    dur = SpeakerDurationResult(
        durations={"Alice": 1.0, "Bob": 1.0},
        eligible_speakers=("Alice", "Bob"),
        speaker_segments={},
        speaker_key_map={},
        total_valid_duration=2.0,
    )
    eq = compute_equity(
        duration_result=dur,
        interruption_initiated={"Bob": 3},
        interruption_received={"Alice": 3},
        interactions=[],
    )
    assert eq["interruption_asymmetry"]["Bob"] == pytest.approx(1.0)
    assert eq["interruption_asymmetry"]["Alice"] == pytest.approx(-1.0)
    assert eq["interruption_asymmetry_index"] == pytest.approx(1.0)
    assert "interruption_balance_index" not in eq
    assert interruption_balance_index(eq["interruption_asymmetry_index"]) == pytest.approx(
        0.0
    )


def test_asymmetry_abstains_without_interruptions() -> None:
    dur = SpeakerDurationResult(
        durations={"Alice": 1.0, "Bob": 1.0},
        eligible_speakers=("Alice", "Bob"),
        speaker_segments={},
        speaker_key_map={},
        total_valid_duration=2.0,
    )
    eq = compute_equity(
        duration_result=dur,
        interruption_initiated={},
        interruption_received={},
        interactions=[],
    )
    assert eq["interruption_asymmetry_index"] is None
    assert any(a["reason"] == ABSTAIN_NO_INTERRUPTIONS for a in eq["abstentions"])


def test_response_latency_attribution_invalid_gaps_and_cv() -> None:
    dur = SpeakerDurationResult(
        durations={"Alice": 1.0, "Bob": 1.0, "Carol": 1.0},
        eligible_speakers=("Alice", "Bob", "Carol"),
        speaker_segments={},
        speaker_key_map={},
        total_valid_duration=3.0,
    )
    events = [
        _event(itype="response", speaker_a="Alice", speaker_b="Bob", gap=1.0),
        _event(itype="response", speaker_a="Alice", speaker_b="Bob", gap=3.0),
        _event(itype="response", speaker_a="Alice", speaker_b="Carol", gap=2.0),
        _event(itype="response", speaker_a="Alice", speaker_b="Carol", gap=-1.0),
        _event(itype="response", speaker_a="Alice", speaker_b="Carol", gap=float("nan")),
    ]
    eq = compute_equity(
        duration_result=dur,
        interruption_initiated={},
        interruption_received={},
        interactions=events,
    )
    assert eq["response_latency"]["Bob"]["count"] == 2
    assert eq["response_latency"]["Bob"]["mean"] == pytest.approx(2.0)
    assert eq["response_latency"]["Carol"]["count"] == 1
    assert eq["response_latency_fairness_index"] is not None
    assert 0.0 <= eq["response_latency_fairness_index"] <= 1.0


def test_latency_abstains_single_responder() -> None:
    dur = SpeakerDurationResult(
        durations={"Alice": 1.0, "Bob": 1.0},
        eligible_speakers=("Alice", "Bob"),
        speaker_segments={},
        speaker_key_map={},
        total_valid_duration=2.0,
    )
    events = [_event(itype="response", speaker_a="Alice", speaker_b="Bob", gap=0.5)]
    eq = compute_equity(
        duration_result=dur,
        interruption_initiated={},
        interruption_received={},
        interactions=events,
    )
    assert eq["response_latency_fairness_index"] is None


def test_empty_equity_schema_stable() -> None:
    eq = empty_equity()
    for key in (
        "floor_share",
        "floor_entropy",
        "floor_equity_index",
        "interruption_asymmetry",
        "interruption_asymmetry_index",
        "response_latency",
        "response_latency_fairness_index",
        "abstentions",
    ):
        assert key in eq
    assert eq["floor_equity_index"] is None
    assert "interruption_balance_index" not in eq


def test_serialize_round_trip() -> None:
    dur = compute_eligible_speaker_durations(
        [
            {"speaker": "Alice", "start": 0.0, "end": 2.0, "text": "a"},
            {"speaker": "Bob", "start": 2.0, "end": 4.0, "text": "b"},
        ]
    )
    events = [_event(itype="interruption_gap", speaker_a="Alice", speaker_b="Bob")]
    analyzer = SpeakerInteractionAnalyzer()
    analysis = analyzer.analyze_interactions(events)
    analysis["equity"] = serialize_equity(
        compute_equity(
            duration_result=dur,
            interruption_initiated=analysis["interruption_initiated"],
            interruption_received=analysis["interruption_received"],
            interactions=events,
        )
    )
    serialized = serialize_interactions_summary(analysis)
    assert serialized["semantics_version"] == INTERACTIONS_SEMANTICS_VERSION
    assert serialized["equity"]["floor_equity_index"] is not None
    assert "interruption_balance_index" not in serialized["equity"]


def test_partial_chart_rendering() -> None:
    svc = MagicMock()
    # Floor only
    create_equity_floor_chart(
        {"equity": {"floor_share": {"Alice": 1.0}, "floor_equity_index": None}},
        svc,
        "sample",
    )
    assert svc.save_chart.called
    floor_spec = svc.save_chart.call_args_list[0].args[0]
    assert floor_spec.viz_id == "interactions.equity.floor.global"

    svc2 = MagicMock()
    create_equity_summary_chart(
        {
            "equity": {
                "floor_equity_index": None,
                "interruption_asymmetry_index": 0.5,
                "response_latency_fairness_index": None,
            }
        },
        svc2,
        "sample",
    )
    assert svc2.save_chart.called
    summary_spec = svc2.save_chart.call_args.args[0]
    assert "Interruption inequity" in summary_spec.categories
    assert "Interruption balance" in summary_spec.categories
    assert "Floor equity" not in summary_spec.categories

    svc3 = MagicMock()
    create_equity_floor_chart({"equity": {"floor_share": {}}}, svc3, "sample")
    svc3.save_chart.assert_not_called()


def _ptr(
    path: str,
    payload: dict[str, Any],
    *,
    run_id: str = "r1",
    order_index: int = 0,
) -> PerTranscriptResult:
    return PerTranscriptResult(
        transcript_path=path,
        transcript_key=path,
        run_id=run_id,
        order_index=order_index,
        output_dir=f"out/{path}",
        module_results={"interactions": {"payload": payload}},
    )


def test_group_nullable_equity_and_semantics_gate() -> None:
    canonical = CanonicalSpeakerMap(
        transcript_to_speakers={
            "a.json": {"Alice": 1, "Bob": 2},
            "b.json": {"Alice": 1, "Bob": 2},
            "legacy.json": {"Alice": 1, "Bob": 2},
        },
        canonical_to_display={1: "Alice", 2: "Bob"},
        transcript_to_display={
            "a.json": {"Alice": "Alice", "Bob": "Bob"},
            "b.json": {"Alice": "Alice", "Bob": "Bob"},
            "legacy.json": {"Alice": "Alice", "Bob": "Bob"},
        },
    )
    tset = TranscriptSet.create(["a.json", "b.json", "legacy.json"], name="Group")

    current = {
        "semantics_version": INTERACTIONS_SEMANTICS_VERSION,
        "interruption_initiated": {"Alice": 1},
        "interruption_received": {"Bob": 1},
        "responses_initiated": {},
        "responses_received": {},
        "dominance_scores": {"Alice": 1.0},
        "total_interactions_count": 1,
        "unique_speakers": 2,
        "equity": {
            "floor_equity_index": 0.8,
            "interruption_asymmetry_index": 0.4,
            "response_latency_fairness_index": None,
            "abstentions": [
                {
                    "metric": "response_latency_fairness_index",
                    "reason": "fewer_than_two_valid_responders",
                }
            ],
        },
    }
    legacy = {
        # missing semantics_version
        "interruption_initiated": {"Alice": 9},
        "interruption_received": {"Bob": 9},
        "responses_initiated": {},
        "responses_received": {},
        "dominance_scores": {"Alice": 1.0},
        "total_interactions_count": 2,
        "unique_speakers": 2,
        "equity": {"floor_equity_index": 0.1},
    }

    # All current → pool ok
    ok = aggregate_interactions_group(
        [
            _ptr("a.json", current, order_index=0),
            _ptr(
                "b.json",
                {**current, "total_interactions_count": 3},
                order_index=1,
            ),
        ],
        canonical,
        tset,
    )
    assert ok is not None
    assert ok["interactions_pooled"]["speakers"]
    assert ok["session_rows"][0]["floor_equity_index"] == pytest.approx(0.8)
    assert ok["session_rows"][0]["response_latency_fairness_index"] is None
    assert "aggregation_warnings" not in ok

    # Mixed → directional pool skipped, session rows kept, one warning
    mixed = aggregate_interactions_group(
        [
            _ptr("a.json", current, order_index=0),
            _ptr("legacy.json", legacy, order_index=1),
        ],
        canonical,
        tset,
    )
    assert mixed is not None
    assert mixed["interactions_pooled"]["speakers"] == []
    assert mixed["speaker_rows"] == []
    assert len(mixed["session_rows"]) == 2
    warnings = mixed["aggregation_warnings"]
    assert len(warnings) == 1
    assert warnings[0]["code"] == "INTERACTIONS_SEMANTICS_VERSION_MISMATCH"
    assert "legacy.json" in warnings[0]["transcripts_affected"]


def test_summary_extractor_equity_and_pairs() -> None:
    summary: dict[str, Any] = {"key_metrics": {}, "notes": []}
    data = {
        "interactions": [
            {"speaker_a": "Alice", "speaker_b": "Bob", "interaction_type": "response"},
            {"speaker_a": "Bob", "speaker_b": "Alice", "interaction_type": "response"},
        ],
        "equity": {
            "floor_equity_index": 0.9,
            "interruption_asymmetry_index": None,
            "response_latency_fairness_index": 0.7,
            "abstentions": [
                {"metric": "interruption_asymmetry_index", "reason": "no_interruptions"}
            ],
        },
    }
    extract_interactions_summary(data, summary)
    assert summary["key_metrics"]["Total Interactions"] == 2
    assert summary["key_metrics"]["Unique Speaker Pairs"] == 1
    assert summary["key_metrics"]["Floor Equity"] == "0.900"
    assert "no_interruptions" in summary["key_metrics"]["Interruption Inequity"]
    assert "diarisation" in summary["notes"][0]
