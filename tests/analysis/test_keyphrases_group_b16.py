"""Additional keyphrases / wordclouds isolation tests for B16."""

from __future__ import annotations

from transcriptx.core.analysis.keyphrases.aggregation import aggregate_keyphrases
from transcriptx.core.analysis.keyphrases.contract import SCHEMA_ID, SEMANTICS_VERSION
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult


class _DummyMap:
    pass


class _DummySet:
    key = "g"
    name = "g"
    metadata: dict = {}


def _ptr(tid: str, phrases: list[dict]) -> PerTranscriptResult:
    return PerTranscriptResult(
        transcript_id=tid,
        module_results={
            "keyphrases": {
                "schema_id": SCHEMA_ID,
                "semantics_version": SEMANTICS_VERSION,
                "usable": True,
                "evaluation_state": "scored",
                "global_by_method": {
                    "noun_chunks": {
                        "method": "noun_chunks",
                        "evaluation_state": "scored",
                        "phrases": phrases,
                    }
                },
            }
        },
    )


def test_group_pool_by_canonical_key_min_sessions() -> None:
    p1 = {
        "phrase": "product roadmap",
        "canonical_key": "product roadmap",
        "token_count": 2,
        "rank": 1,
        "raw_score": 2.0,
        "score_direction": "higher_is_better",
        "rank_weight": 1.0,
        "occurrence_count": 2,
        "segment_support": 2,
    }
    p2 = {
        "phrase": "product roadmap",
        "canonical_key": "product roadmap",
        "token_count": 2,
        "rank": 1,
        "raw_score": 1.5,
        "score_direction": "higher_is_better",
        "rank_weight": 0.8,
        "occurrence_count": 1,
        "segment_support": 1,
    }
    singleton = {
        "phrase": "one session only",
        "canonical_key": "one session only",
        "token_count": 3,
        "rank": 2,
        "raw_score": 1.0,
        "score_direction": "higher_is_better",
        "rank_weight": 0.5,
        "occurrence_count": 5,
        "segment_support": 3,
    }
    out = aggregate_keyphrases(
        [_ptr("a", [p1, singleton]), _ptr("b", [p2])],
        _DummyMap(),  # type: ignore[arg-type]
        _DummySet(),  # type: ignore[arg-type]
    )
    assert out is not None
    pool = out["keyphrase_noun_chunk_pool"]
    keys = {row["canonical_key"] for row in pool}
    assert "product roadmap" in keys
    assert "one session only" not in keys
    row = next(r for r in pool if r["canonical_key"] == "product roadmap")
    assert row["member_session_support"] == 2
    assert row["occurrence_count"] == 3


def test_wordclouds_optional_dep_not_hard() -> None:
    from transcriptx.core.pipeline.module_registry import get_module_info

    wc = get_module_info("wordclouds")
    assert "keyphrases" not in (wc.dependencies or [])
    assert "keyphrases" in (wc.optional_dependencies or [])
