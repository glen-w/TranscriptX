"""Unit tests for keyphrases scoring, contract, and isolation semantics."""

from __future__ import annotations

from transcriptx.core.analysis.keyphrases.contract import (
    SCHEMA_ID,
    SEMANTICS_VERSION,
    KeyphrasesResult,
    RankedPhrase,
    SkippedMethod,
)
from transcriptx.core.analysis.keyphrases.scoring import (
    assign_ranks_and_weights,
    base_salience,
    higher_is_better_salience,
    min_max_weights,
)
from transcriptx.core.analysis.wordclouds.keyphrase_clouds import (
    _freq_from_phrases,
    _validate_upstream,
    emit_keyphrase_wordclouds,
)


def test_base_salience_uses_occurrence_and_support() -> None:
    a = base_salience(occurrence_count=2, segment_support=1, token_count=2)
    b = base_salience(occurrence_count=2, segment_support=3, token_count=2)
    assert b > a


def test_yake_direction_conversion() -> None:
    assert higher_is_better_salience(0.1, "lower_is_better") > higher_is_better_salience(
        0.9, "lower_is_better"
    )


def test_assign_ranks_deterministic_tiebreak() -> None:
    phrases = [
        RankedPhrase(
            phrase="alpha plan",
            canonical_key="alpha plan",
            token_count=2,
            rank=1,
            raw_score=1.0,
            score_direction="higher_is_better",
            rank_weight=0.0,
            occurrence_count=2,
            segment_support=2,
        ),
        RankedPhrase(
            phrase="beta plan",
            canonical_key="beta plan",
            token_count=2,
            rank=1,
            raw_score=1.0,
            score_direction="higher_is_better",
            rank_weight=0.0,
            occurrence_count=2,
            segment_support=2,
        ),
    ]
    ranked = assign_ranks_and_weights(phrases)
    assert [p.canonical_key for p in ranked] == ["alpha plan", "beta plan"]
    assert ranked[0].rank == 1 and ranked[1].rank == 2
    assert all(p.rank_weight == 1.0 for p in ranked)


def test_min_max_weights_single_value() -> None:
    assert min_max_weights([3.0]) == [1.0]


def test_drop_non_positive_cloud_weights() -> None:
    freq, _ = _freq_from_phrases(
        [
            {"phrase": "good", "rank_weight": 0.5, "token_count": 1},
            {"phrase": "zero", "rank_weight": 0.0, "token_count": 1},
            {"phrase": "neg", "rank_weight": -0.2, "token_count": 1},
        ]
    )
    assert freq == {"good": 0.5}


def test_stale_upstream_schema_skipped() -> None:
    assert _validate_upstream({"schema_id": "other.v1"}) is None
    skipped = emit_keyphrase_wordclouds(
        {"schema_id": "stale", "semantics_version": SEMANTICS_VERSION},
        output_structure=None,
        base_name="t",
    )
    assert skipped
    assert all(s["reason"] == "upstream_missing_or_stale_schema" for s in skipped)


def test_keyphrases_result_primary_phrases_alias() -> None:
    result = KeyphrasesResult(
        usable=True,
        evaluation_state="scored",
        methods_run=["noun_chunks"],
        skipped_methods=[],
        global_by_method={
            "noun_chunks": {
                "method": "noun_chunks",
                "evaluation_state": "scored",
                "phrases": [
                    {
                        "phrase": "roadmap review",
                        "canonical_key": "roadmap review",
                        "token_count": 2,
                        "rank": 1,
                        "raw_score": 1.5,
                        "score_direction": "higher_is_better",
                        "rank_weight": 1.0,
                        "occurrence_count": 3,
                        "segment_support": 2,
                        "evidence": [],
                    }
                ],
            }
        },
        speakers_by_method={},
        metadata={"schema_id": SCHEMA_ID},
    )
    assert result.primary_phrases[0].phrase == "roadmap review"


def test_skipped_method_reason_codes() -> None:
    skip = SkippedMethod(method="keybert", reason_code="model_unavailable")
    assert skip.reason_code == "model_unavailable"
