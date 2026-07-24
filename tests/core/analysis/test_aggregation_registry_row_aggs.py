"""Deeper offline coverage for aggregation registry row aggregators and deps."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.core.analysis.aggregation.registry import (
    _aggregate_acts,
    _aggregate_affect_tension,
    _aggregate_understandability,
    build_registry,
)
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap


def _ts(tmp_path: Path) -> TranscriptSet:
    return TranscriptSet.create([str(tmp_path / "a.json")], name="G", key="gk")


def _sm() -> CanonicalSpeakerMap:
    return CanonicalSpeakerMap(
        transcript_to_speakers={},
        canonical_to_display={},
        transcript_to_display={},
    )


def _result(tmp_path: Path, module_results: dict) -> PerTranscriptResult:
    return PerTranscriptResult(
        transcript_path=str(tmp_path / "a.json"),
        transcript_key="a",
        run_id="r1",
        order_index=0,
        output_dir=str(tmp_path),
        module_results=module_results,
    )


@pytest.mark.unit
def test_build_registry_expected_dep_edges() -> None:
    by_id = {e.agg_id: e for e in build_registry()}
    assert by_id["entity_sentiment"].deps == ["ner"]
    assert by_id["pauses"].deps == ["acts"]
    assert by_id["momentum"].deps == ["pauses"]
    assert by_id["affect_tension"].deps == ["emotion", "sentiment"]
    assert by_id["contagion"].deps == ["emotion"]
    assert by_id["qa_analysis"].deps == ["acts"]
    assert set(by_id["moments"].deps) == {
        "pauses",
        "echoes",
        "momentum",
        "qa_analysis",
    }
    assert by_id["summary"].deps == ["highlights"]
    assert by_id["summary"].output_type == "blob"
    assert by_id["insight_eligibility"].deps == ["tics"]
    assert by_id["transcript_output"].output_type == "blob"
    assert "voice_contours" in by_id
    assert "simplified_transcript" in by_id
    assert "bertopic" in by_id
    assert by_id["bertopic"].deps == []
    assert by_id["bertopic"].selector(["bertopic"]) is True
    assert by_id["bertopic"].selector(["topic_modeling"]) is False


@pytest.mark.unit
def test_build_registry_selectors_for_alias_modules() -> None:
    by_id = {e.agg_id: e for e in build_registry()}
    assert by_id["semantic_similarity"].selector(["semantic_similarity"]) is True
    assert by_id["semantic_similarity"].selector(["stats"]) is False
    assert by_id["prosody"].selector(["voice_features"]) is True
    assert by_id["prosody"].selector(["voice_mismatch"]) is False


@pytest.mark.unit
def test_aggregate_acts_success_and_bad_shape(tmp_path: Path) -> None:
    sm, ts = _sm(), _ts(tmp_path)
    bad = _aggregate_acts(
        [
            _result(
                tmp_path,
                {"acts": {"payload": {"global_stats": "bad", "speaker_stats": {}}}},
            )
        ],
        sm,
        ts,
    )
    assert bad is not None
    assert bad["warning"]["aggregation_key"] == "acts"

    good = _aggregate_acts(
        [
            _result(
                tmp_path,
                {
                    "acts": {
                        "payload": {
                            "global_stats": {"n_acts": 3},
                            "speaker_stats": {"Alice": {"n_acts": 2}},
                        }
                    }
                },
            )
        ],
        sm,
        ts,
    )
    assert good is not None
    assert "warning" not in good
    assert len(good["session_rows"]) == 1
    assert good["session_rows"][0]["n_acts"] == 3
    assert len(good["speaker_rows"]) >= 1


@pytest.mark.unit
def test_aggregate_understandability_none_when_empty(tmp_path: Path) -> None:
    assert (
        _aggregate_understandability([_result(tmp_path, {})], _sm(), _ts(tmp_path))
        is None
    )


@pytest.mark.unit
def test_aggregate_understandability_success(tmp_path: Path) -> None:
    out = _aggregate_understandability(
        [
            _result(
                tmp_path,
                {
                    "understandability": {
                        "payload": {
                            "global_stats": {"score": 0.8},
                            "speaker_stats": {"Alice": {"score": 0.9}},
                        }
                    }
                },
            )
        ],
        _sm(),
        _ts(tmp_path),
    )
    assert out is not None
    assert out["session_rows"][0]["score"] == 0.8


@pytest.mark.unit
def test_aggregate_affect_tension_warning_and_success(tmp_path: Path) -> None:
    sm, ts = _sm(), _ts(tmp_path)
    warn = _aggregate_affect_tension(
        [
            _result(
                tmp_path,
                {"affect_tension": {"payload": {"derived_indices": "bad"}}},
            )
        ],
        sm,
        ts,
    )
    assert warn is not None
    assert warn["warning"]["aggregation_key"] == "affect_tension"

    out = _aggregate_affect_tension(
        [
            _result(
                tmp_path,
                {
                    "affect_tension": {
                        "payload": {
                            "derived_indices": {
                                "global": {"tension": 0.4},
                                "by_speaker": {"Alice": {"tension": 0.5}},
                            }
                        }
                    }
                },
            )
        ],
        sm,
        ts,
    )
    assert out is not None
    assert out["session_rows"][0]["tension"] == 0.4
    assert any(r.get("tension") == 0.5 for r in out["speaker_rows"])
