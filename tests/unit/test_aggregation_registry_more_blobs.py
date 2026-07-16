"""More offline unit coverage for aggregation registry blob/row helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.aggregation.registry import (
    _aggregate_contagion,
    _aggregate_conversation_loops,
    _aggregate_echoes,
    _aggregate_highlights,
    _aggregate_lexical_diversity,
    _aggregate_momentum,
    _aggregate_pauses,
    _aggregate_qa_analysis,
    _aggregate_temporal_dynamics,
    _aggregate_tics,
    _aggregate_wordclouds,
)
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap


def _ts(tmp_path: Path, **meta) -> TranscriptSet:
    ts = TranscriptSet.create([str(tmp_path / "a.json")], name="G", key="gk")
    ts.metadata.update(meta)
    return ts


def _sm() -> CanonicalSpeakerMap:
    return CanonicalSpeakerMap(
        transcript_to_speakers={},
        canonical_to_display={},
        transcript_to_display={},
    )


def _result(
    tmp_path: Path, module_results: dict, key: str = "a"
) -> PerTranscriptResult:
    return PerTranscriptResult(
        transcript_path=str(tmp_path / f"{key}.json"),
        transcript_key=key,
        run_id="r1",
        order_index=0,
        output_dir=str(tmp_path),
        module_results=module_results,
    )


@pytest.mark.unit
def test_aggregate_wordclouds_missing_group_dir(tmp_path: Path) -> None:
    result = _result(tmp_path, {"wordclouds": {"payload": {"x": 1}}})
    with (
        patch(
            "transcriptx.core.analysis.aggregation.wordclouds.aggregate_wordclouds_group",
            return_value=({"Alice": ["hi"]}, {"speaker_count": 1}),
        ),
        patch(
            "transcriptx.core.analysis.wordclouds.analysis.run_group_wordclouds",
            MagicMock(),
        ),
    ):
        out = _aggregate_wordclouds([result], _sm(), _ts(tmp_path))
    assert out is not None
    assert out["warning"]["aggregation_key"] == "wordclouds"


@pytest.mark.unit
def test_aggregate_wordclouds_runs_group_and_merges_extra(tmp_path: Path) -> None:
    result = _result(tmp_path, {"wordclouds": {"payload": {"x": 1}}})
    ts = _ts(
        tmp_path,
        group_output_dir=str(tmp_path / "group"),
        group_uuid="g-uuid",
        group_run_id="gr1",
    )
    (tmp_path / "group").mkdir()
    extra = {
        "pooled_cross_session_summary_path": "/tmp/pooled.json",
        "skipped_variants": ["v1"],
    }
    with (
        patch(
            "transcriptx.core.analysis.aggregation.wordclouds.aggregate_wordclouds_group",
            return_value=(
                {"Alice": ["hi"]},
                {"speaker_count": 1, "skipped_variants": ["v0"]},
            ),
        ),
        patch(
            "transcriptx.core.analysis.wordclouds.analysis.run_group_wordclouds",
            return_value=extra,
        ) as run_wc,
    ):
        out = _aggregate_wordclouds([result], _sm(), ts)
    run_wc.assert_called_once()
    assert out is not None
    assert out["session_rows"][0]["speaker_count"] == 1
    assert (
        out["session_rows"][0]["pooled_cross_session_summary_path"]
        == "/tmp/pooled.json"
    )
    assert out["session_rows"][0]["skipped_variants"] == ["v0", "v1"]


@pytest.mark.unit
def test_aggregate_wordclouds_none_when_no_summary(tmp_path: Path) -> None:
    result = _result(tmp_path, {})
    with patch(
        "transcriptx.core.analysis.aggregation.wordclouds.aggregate_wordclouds_group",
        return_value=(None, None),
    ):
        assert _aggregate_wordclouds([result], _sm(), _ts(tmp_path)) is None


@pytest.mark.unit
def test_warning_paths_for_blob_helpers(tmp_path: Path) -> None:
    sm, ts = _sm(), _ts(tmp_path)

    assert (
        _aggregate_pauses(
            [
                _result(
                    tmp_path,
                    {"pauses": {"payload": {"stats": "bad", "speaker_stats": {}}}},
                )
            ],
            sm,
            ts,
        )["warning"]["aggregation_key"]
        == "pauses"
    )

    assert (
        _aggregate_momentum(
            [_result(tmp_path, {"momentum": {"payload": {"stats": "bad"}}})],
            sm,
            ts,
        )["warning"]["aggregation_key"]
        == "momentum"
    )

    assert (
        _aggregate_contagion(
            [
                _result(
                    tmp_path,
                    {"contagion": {"payload": {"contagion_summary": "bad"}}},
                )
            ],
            sm,
            ts,
        )["warning"]["aggregation_key"]
        == "contagion"
    )

    assert (
        _aggregate_conversation_loops(
            [
                _result(
                    tmp_path,
                    {"conversation_loops": {"payload": {"summary": "bad"}}},
                )
            ],
            sm,
            ts,
        )["warning"]["aggregation_key"]
        == "conversation_loops"
    )

    # temporal_dynamics non-dict payload is filtered by extract_payload; force via patch
    with patch(
        "transcriptx.core.analysis.aggregation.registry._extract_payload",
        return_value=["not-a-dict"],
    ):
        assert (
            _aggregate_temporal_dynamics(
                [_result(tmp_path, {"temporal_dynamics": {"payload": {}}})],
                sm,
                ts,
            )["warning"]["aggregation_key"]
            == "temporal_dynamics"
        )

    assert (
        _aggregate_qa_analysis(
            [_result(tmp_path, {"qa_analysis": {"payload": {"statistics": "bad"}}})],
            sm,
            ts,
        )["warning"]["aggregation_key"]
        == "qa_analysis"
    )

    assert (
        _aggregate_lexical_diversity(
            [
                _result(
                    tmp_path,
                    {
                        "lexical_diversity": {
                            "payload": {"global_stats": "bad", "speaker_stats": {}}
                        }
                    },
                )
            ],
            sm,
            ts,
        )["warning"]["aggregation_key"]
        == "lexical_diversity"
    )

    assert (
        _aggregate_tics(
            [
                _result(
                    tmp_path,
                    {"tics": {"payload": {"global_stats": "bad", "speaker_stats": {}}}},
                )
            ],
            sm,
            ts,
        )["warning"]["aggregation_key"]
        == "tics"
    )


@pytest.mark.unit
def test_aggregate_contagion_with_aggregation_warnings(
    tmp_path: Path, monkeypatch
) -> None:
    result = _result(
        tmp_path,
        {
            "contagion": {
                "payload": {
                    "contagion_summary": {"pair": 1},
                    "speaker_emotions": {"Alice": {"joy": 1}},
                }
            }
        },
    )
    monkeypatch.setattr(
        "transcriptx.core.analysis.aggregation.registry.build_contagion_pooled_for_group",
        lambda *a, **k: ({"pooled": True}, [{"code": "W"}]),
    )
    out = _aggregate_contagion([result], _sm(), _ts(tmp_path))
    assert out is not None
    assert out["contagion_pooled"] == {"pooled": True}
    assert out["aggregation_warnings"] == [{"code": "W"}]


@pytest.mark.unit
def test_aggregate_echoes_skips_non_dict_speaker_counts(tmp_path: Path) -> None:
    result = _result(
        tmp_path,
        {
            "echoes": {
                "payload": {
                    "stats": {
                        "echo_count": 2,
                        "counts_by_speaker": {"Alice": {"echo": 2}, "Bob": "bad"},
                    }
                }
            }
        },
    )
    out = _aggregate_echoes([result], _sm(), _ts(tmp_path))
    assert out is not None
    assert len(out["speaker_rows"]) == 1
    assert out["speaker_rows"][0]["echo"] == 2


@pytest.mark.unit
def test_aggregate_highlights_none_and_score_variants(tmp_path: Path) -> None:
    assert _aggregate_highlights([_result(tmp_path, {})], _sm(), _ts(tmp_path)) is None

    result = _result(
        tmp_path,
        {
            "highlights": {
                "payload": {
                    "sections": {
                        "cold_open": {
                            "items": [
                                {
                                    "text": "hi",
                                    "start": 0,
                                    "end": 1,
                                    "speaker": "Alice",
                                    "score": {"total": 0.5},
                                }
                            ]
                        }
                    }
                },
                "artifacts": [{"path": "highlights/highlights.json"}],
            }
        },
    )
    out = _aggregate_highlights([result], _sm(), _ts(tmp_path))
    assert out is not None
    assert out["content_rows"][0]["score"] == 0.5


@pytest.mark.unit
def test_aggregate_helpers_return_none_empty(tmp_path: Path) -> None:
    empty = _result(tmp_path, {})
    sm, ts = _sm(), _ts(tmp_path)
    assert _aggregate_contagion([empty], sm, ts) is None
    assert _aggregate_qa_analysis([empty], sm, ts) is None
    assert _aggregate_echoes([empty], sm, ts) is None
    assert _aggregate_tics([empty], sm, ts) is None
