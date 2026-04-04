"""Unit tests for stats group aggregation (``aggregate_stats_group``)."""

from __future__ import annotations

import pytest

from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap
from transcriptx.core.analysis.stats.aggregation import aggregate_stats_group


def _ts() -> TranscriptSet:
    return TranscriptSet.create(["/a/s1.json", "/a/s2.json"], name="G", key="gk")


def _map_same_alice() -> CanonicalSpeakerMap:
    cid = 101
    return CanonicalSpeakerMap(
        transcript_to_speakers={
            "/a/s1.json": {"1": cid},
            "/a/s2.json": {"1": cid},
        },
        canonical_to_display={cid: "Alice"},
        transcript_to_display={
            "/a/s1.json": {"1": "Alice"},
            "/a/s2.json": {"1": "Alice"},
        },
    )


def _stats_payload(speaker_stats: list, sentiment_summary: dict | None = None) -> dict:
    return {
        "speaker_stats": speaker_stats,
        "sentiment_summary": sentiment_summary or {},
    }


@pytest.mark.unit
def test_aggregate_stats_group_empty_returns_none() -> None:
    out = aggregate_stats_group(
        [],
        _map_same_alice(),
        _ts(),
    )
    assert out is None


@pytest.mark.unit
def test_aggregate_stats_group_accepts_results_key_not_only_payload() -> None:
    """Module envelope may store rows under ``results`` instead of ``payload``."""
    results = [
        PerTranscriptResult(
            transcript_path="/a/s1.json",
            transcript_key="s1",
            run_id="r1",
            order_index=0,
            output_dir="out/s1",
            module_results={
                "stats": {
                    "results": _stats_payload(
                        [(5.0, "Alice", 20, 2, 0.05, 0.0)],
                        {
                            "Alice": {
                                "compound": 0.1,
                                "pos": 0.2,
                                "neu": 0.7,
                                "neg": 0.0,
                            }
                        },
                    )
                }
            },
        )
    ]
    out = aggregate_stats_group(results, _map_same_alice(), _ts())
    assert out is not None
    assert len(out["session_rows"]) == 1
    assert out["session_rows"][0]["total_words"] == 20


@pytest.mark.unit
def test_aggregate_stats_group_merges_same_canonical_across_sessions() -> None:
    results = [
        PerTranscriptResult(
            transcript_path="/a/s1.json",
            transcript_key="s1",
            run_id="r1",
            order_index=0,
            output_dir="out/s1",
            module_results={
                "stats": {
                    "payload": _stats_payload(
                        [(10.0, "Alice", 100, 10, 0.0, 0.0)],
                    )
                }
            },
        ),
        PerTranscriptResult(
            transcript_path="/a/s2.json",
            transcript_key="s2",
            run_id="r2",
            order_index=1,
            output_dir="out/s2",
            module_results={
                "stats": {
                    "payload": _stats_payload(
                        [(5.0, "Alice", 50, 5, 0.0, 0.0)],
                    )
                }
            },
        ),
    ]
    out = aggregate_stats_group(results, _map_same_alice(), _ts())
    assert out is not None
    speakers = out["speaker_rows"]
    assert len(speakers) == 1
    row = speakers[0]
    assert row["total_word_count"] == 150
    assert row["total_segment_count"] == 15
    assert row["total_duration"] == pytest.approx(15.0)
    pooled = out["stats_pooled"]
    assert pooled["total_words"] == 150
    assert pooled["total_segments"] == 15


@pytest.mark.unit
def test_aggregate_stats_group_stats_pooled_sums_per_session_totals() -> None:
    results = [
        PerTranscriptResult(
            transcript_path="/a/s1.json",
            transcript_key="s1",
            run_id="r1",
            order_index=0,
            output_dir="o1",
            module_results={
                "stats": {"payload": _stats_payload([(1.0, "Alice", 10, 1, 0.0, 0.0)])}
            },
        ),
        PerTranscriptResult(
            transcript_path="/a/s2.json",
            transcript_key="s2",
            run_id="r2",
            order_index=1,
            output_dir="o2",
            module_results={
                "stats": {"payload": _stats_payload([(1.0, "Bob", 30, 3, 0.0, 0.0)])}
            },
        ),
    ]
    cmap = CanonicalSpeakerMap(
        transcript_to_speakers={
            "/a/s1.json": {"1": 1},
            "/a/s2.json": {"2": 2},
        },
        canonical_to_display={1: "Alice", 2: "Bob"},
        transcript_to_display={
            "/a/s1.json": {"1": "Alice"},
            "/a/s2.json": {"2": "Bob"},
        },
    )
    out = aggregate_stats_group(results, cmap, _ts())
    assert out is not None
    pooled = out["stats_pooled"]
    assert pooled["total_words"] == 40
    assert pooled["total_segments"] == 4


@pytest.mark.unit
def test_aggregate_stats_group_tic_rate_weighted_by_word_count() -> None:
    """tic_rate is total tic_count / total words after merging speakers."""
    results = [
        PerTranscriptResult(
            transcript_path="/a/s1.json",
            transcript_key="s1",
            run_id="r1",
            order_index=0,
            output_dir="o1",
            module_results={
                "stats": {
                    "payload": _stats_payload([(1.0, "Alice", 100, 1, 0.10, 0.0)])
                }
            },
        ),
        PerTranscriptResult(
            transcript_path="/a/s2.json",
            transcript_key="s2",
            run_id="r2",
            order_index=1,
            output_dir="o2",
            module_results={
                "stats": {"payload": _stats_payload([(1.0, "Alice", 50, 1, 0.20, 0.0)])}
            },
        ),
    ]
    out = aggregate_stats_group(results, _map_same_alice(), _ts())
    assert out is not None
    spk = out["speaker_rows"][0]
    # 100*0.1 + 50*0.2 = 20; 20/150
    assert spk["tic_rate"] == pytest.approx(20.0 / 150.0)
