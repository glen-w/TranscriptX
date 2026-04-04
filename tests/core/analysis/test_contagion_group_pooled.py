"""Tests for edge-pooled contagion group merge."""

from __future__ import annotations

from transcriptx.core.analysis.aggregation.contagion import (
    build_contagion_pooled_for_group,
)
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap


def _map_ab() -> CanonicalSpeakerMap:
    return CanonicalSpeakerMap(
        transcript_to_speakers={
            "a.json": {"Alice": 1, "Bob": 2},
            "b.json": {"Alice": 1, "Bob": 2},
        },
        canonical_to_display={1: "Alice", 2: "Bob"},
        transcript_to_display={
            "a.json": {"Alice": "Alice", "Bob": "Bob"},
            "b.json": {"Alice": "Alice", "Bob": "Bob"},
        },
    )


def test_build_contagion_pooled_merges_directed_pairs_across_sessions() -> None:
    cmap = _map_ab()
    results = [
        PerTranscriptResult(
            transcript_path="a.json",
            transcript_key="a",
            run_id="r1",
            order_index=0,
            output_dir="out/a",
            module_results={
                "contagion": {
                    "payload": {"contagion_summary": {"Alice->Bob": {"joy": 1}}}
                }
            },
        ),
        PerTranscriptResult(
            transcript_path="b.json",
            transcript_key="b",
            run_id="r2",
            order_index=1,
            output_dir="out/b",
            module_results={
                "contagion": {
                    "payload": {
                        "contagion_summary": {
                            "Alice->Bob": {"joy": 2, "neutral": 1},
                        }
                    }
                }
            },
        ),
    ]
    pooled, warns = build_contagion_pooled_for_group(results, cmap)
    assert pooled["schema_version"] == 1
    assert len(pooled["edges"]) == 1
    e = pooled["edges"][0]
    assert e["from_canonical_id"] == 1
    assert e["to_canonical_id"] == 2
    assert e["total"] == 4
    assert e["emotions"].get("joy") == 3
    assert e["emotions"].get("neutral") == 1
    assert not warns


def test_build_contagion_pooled_drops_self_edge_with_warning() -> None:
    cmap = _map_ab()
    results = [
        PerTranscriptResult(
            transcript_path="a.json",
            transcript_key="a",
            run_id="r1",
            order_index=0,
            output_dir="out/a",
            module_results={
                "contagion": {
                    "payload": {"contagion_summary": {"Alice->Alice": {"joy": 1}}}
                }
            },
        ),
    ]
    pooled, warns = build_contagion_pooled_for_group(results, cmap)
    assert pooled["edges"] == []
    assert any(w.get("code") == "RELATIONAL_POOL_SELF_EDGE" for w in warns)


def test_build_contagion_pooled_invalid_key_emits_parse_warning() -> None:
    cmap = _map_ab()
    results = [
        PerTranscriptResult(
            transcript_path="a.json",
            transcript_key="a",
            run_id="r1",
            order_index=0,
            output_dir="out/a",
            module_results={
                "contagion": {"payload": {"contagion_summary": {"not_a_pair": {}}}}
            },
        ),
    ]
    pooled, warns = build_contagion_pooled_for_group(results, cmap)
    assert pooled["edges"] == []
    assert any(w.get("code") == "RELATIONAL_POOL_PARSE" for w in warns)
