"""Unit tests for tics group aggregation (registry ``_aggregate_tics``)."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.aggregation.registry import _aggregate_tics
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap


def _ts() -> TranscriptSet:
    return TranscriptSet.create(["/x/a.json", "/x/b.json"], name="G", key="gk")


def _cmap() -> CanonicalSpeakerMap:
    return CanonicalSpeakerMap(
        transcript_to_speakers={"/x/a.json": {"1": 7}, "/x/b.json": {"1": 7}},
        canonical_to_display={7: "Alice"},
        transcript_to_display={
            "/x/a.json": {"1": "Alice"},
            "/x/b.json": {"1": "Alice"},
        },
    )


@pytest.mark.unit
def test_aggregate_tics_group_pooled_sums_total_and_merges_by_tic() -> None:
    results = [
        PerTranscriptResult(
            transcript_path="/x/a.json",
            transcript_key="a",
            run_id="r1",
            order_index=0,
            output_dir="o1",
            module_results={
                "tics": {
                    "payload": {
                        "global_stats": {
                            "total_tics": 4,
                            "um": 3,
                            "like": 1,
                        },
                        "speaker_stats": {
                            "Alice": {"count": 4},
                        },
                    }
                }
            },
        ),
        PerTranscriptResult(
            transcript_path="/x/b.json",
            transcript_key="b",
            run_id="r2",
            order_index=1,
            output_dir="o2",
            module_results={
                "tics": {
                    "payload": {
                        "global_stats": {
                            "total_tics": 6,
                            "um": 2,
                            "uh": 4,
                        },
                        "speaker_stats": {
                            "Alice": {"count": 6},
                        },
                    }
                }
            },
        ),
    ]
    out = _aggregate_tics(results, _cmap(), _ts())
    assert out is not None
    pooled = out["tics_pooled"]
    assert pooled["schema_version"] == 1
    assert pooled["total_tics"] == 10
    by_tic = pooled["by_tic"]
    assert by_tic["uh"] == 4
    assert by_tic["um"] == 5
    assert by_tic["like"] == 1
    assert len(out["session_rows"]) == 2


@pytest.mark.unit
def test_aggregate_tics_group_returns_none_when_no_payload_sessions() -> None:
    results = [
        PerTranscriptResult(
            transcript_path="/x/a.json",
            transcript_key="a",
            run_id="r1",
            order_index=0,
            output_dir="o1",
            module_results={},
        )
    ]
    assert _aggregate_tics(results, _cmap(), _ts()) is None


@pytest.mark.unit
def test_aggregate_tics_accepts_results_envelope_key() -> None:
    results = [
        PerTranscriptResult(
            transcript_path="/x/a.json",
            transcript_key="a",
            run_id="r1",
            order_index=0,
            output_dir="o1",
            module_results={
                "tics": {
                    "results": {
                        "global_stats": {"total_tics": 1, "x": 1},
                        "speaker_stats": {"Alice": {"count": 1}},
                    }
                }
            },
        )
    ]
    out = _aggregate_tics(results, _cmap(), _ts())
    assert out is not None
    assert out["tics_pooled"]["total_tics"] == 1
    assert out["tics_pooled"]["by_tic"]["x"] == 1
