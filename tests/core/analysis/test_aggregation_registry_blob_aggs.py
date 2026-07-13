"""Unit tests for blob/row `_aggregate_*` helpers in the aggregation registry."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.core.analysis.aggregation.registry import (
    _aggregate_acts,
    _aggregate_affect_tension,
    _aggregate_contagion,
    _aggregate_conversation_loops,
    _aggregate_echoes,
    _aggregate_highlights,
    _aggregate_lexical_diversity,
    _aggregate_momentum,
    _aggregate_pauses,
    _aggregate_qa_analysis,
    _aggregate_temporal_dynamics,
    _aggregate_understandability,
)
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap


def _transcript_set(tmp_path: Path) -> TranscriptSet:
    return TranscriptSet.create(
        [str(tmp_path / "a.json")],
        name="G",
        key="gk",
    )


def _speaker_map() -> CanonicalSpeakerMap:
    return CanonicalSpeakerMap(
        transcript_to_speakers={},
        canonical_to_display={},
        transcript_to_display={},
    )


def _result(
    tmp_path: Path,
    module_results: dict,
    *,
    key: str = "a",
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
def test_aggregate_acts_success_and_warning(tmp_path: Path) -> None:
    ok = _result(
        tmp_path,
        {
            "acts": {
                "payload": {
                    "global_stats": {"total_acts": 3},
                    "speaker_stats": {"Alice": {"total_acts": 2}},
                }
            }
        },
    )
    out = _aggregate_acts([ok], _speaker_map(), _transcript_set(tmp_path))
    assert out is not None
    assert "warning" not in out
    assert len(out["session_rows"]) == 1
    assert out["session_rows"][0]["total_acts"] == 3
    assert len(out["speaker_rows"]) == 1

    bad = _result(
        tmp_path,
        {"acts": {"payload": {"global_stats": "nope", "speaker_stats": {}}}},
    )
    warn = _aggregate_acts([bad], _speaker_map(), _transcript_set(tmp_path))
    assert warn is not None
    assert warn["warning"]["aggregation_key"] == "acts"


@pytest.mark.unit
def test_aggregate_pauses_success(tmp_path: Path) -> None:
    result = _result(
        tmp_path,
        {
            "pauses": {
                "payload": {
                    "stats": {"pause_count": 4},
                    "speaker_stats": {"Bob": {"pause_count": 1}},
                }
            }
        },
    )
    out = _aggregate_pauses([result], _speaker_map(), _transcript_set(tmp_path))
    assert out is not None
    assert out["session_rows"][0]["pause_count"] == 4
    assert len(out["speaker_rows"]) == 1


@pytest.mark.unit
def test_aggregate_echoes_success_and_warning(tmp_path: Path) -> None:
    ok = _result(
        tmp_path,
        {
            "echoes": {
                "payload": {
                    "stats": {
                        "echo_count": 2,
                        "counts_by_speaker": {"Alice": {"echo_count": 2}},
                    }
                }
            }
        },
    )
    out = _aggregate_echoes([ok], _speaker_map(), _transcript_set(tmp_path))
    assert out is not None
    assert out["session_rows"][0]["echo_count"] == 2
    assert len(out["speaker_rows"]) == 1
    assert out["speaker_rows"][0]["echo_count"] == 2

    bad = _result(
        tmp_path,
        {
            "echoes": {
                "payload": {
                    "stats": {
                        "echo_count": 1,
                        "counts_by_speaker": "not-a-dict",
                    }
                }
            }
        },
    )
    warn = _aggregate_echoes([bad], _speaker_map(), _transcript_set(tmp_path))
    assert warn is not None
    assert warn["warning"]["aggregation_key"] == "echoes"


@pytest.mark.unit
def test_aggregate_highlights_builds_content_rows(tmp_path: Path) -> None:
    result = _result(
        tmp_path,
        {
            "highlights": {
                "payload": {
                    "sections": {
                        "cold_open": {
                            "items": [
                                {
                                    "text": "opening line",
                                    "start": 0.0,
                                    "end": 1.5,
                                    "speaker": "Alice",
                                    "score": {"total": 0.9},
                                }
                            ]
                        },
                        "conflict_points": {
                            "events": [
                                {
                                    "anchor_quote": {
                                        "text": "conflict bit",
                                        "start": 2.0,
                                        "end": 3.0,
                                    }
                                }
                            ]
                        },
                    }
                },
                "artifacts": [{"relative_path": "highlights/highlights.json"}],
            }
        },
    )
    out = _aggregate_highlights([result], _speaker_map(), _transcript_set(tmp_path))
    assert out is not None
    assert out["content_rows_name"] == "highlight_rows"
    assert len(out["content_rows"]) == 2
    assert out["content_rows"][0]["text"] == "opening line"
    assert out["content_rows"][0]["score"] == 0.9


@pytest.mark.unit
def test_aggregate_lexical_diversity_and_understandability(tmp_path: Path) -> None:
    lex = _result(
        tmp_path,
        {
            "lexical_diversity": {
                "payload": {
                    "global_stats": {"ttr": 0.4, "token_count": 100},
                    "speaker_stats": {"Alice": {"ttr": 0.5}},
                }
            }
        },
    )
    lex_out = _aggregate_lexical_diversity(
        [lex], _speaker_map(), _transcript_set(tmp_path)
    )
    assert lex_out is not None
    assert "aggregation_note" in lex_out
    assert lex_out["session_rows"][0]["ttr"] == 0.4

    und = _result(
        tmp_path,
        {
            "understandability": {
                "payload": {
                    "global_stats": {"score": 0.8},
                    "speaker_stats": {},
                }
            }
        },
    )
    und_out = _aggregate_understandability(
        [und], _speaker_map(), _transcript_set(tmp_path)
    )
    assert und_out is not None
    assert und_out["session_rows"][0]["score"] == 0.8

    bad = _result(
        tmp_path,
        {
            "understandability": {
                "payload": {"global_stats": "not-a-dict", "speaker_stats": {}}
            }
        },
    )
    warn = _aggregate_understandability(
        [bad], _speaker_map(), _transcript_set(tmp_path)
    )
    assert warn is not None
    assert warn["warning"]["aggregation_key"] == "understandability"


@pytest.mark.unit
def test_aggregate_affect_tension_success_and_warning(tmp_path: Path) -> None:
    ok = _result(
        tmp_path,
        {
            "affect_tension": {
                "payload": {
                    "derived_indices": {
                        "global": {"tension": 0.3},
                        "by_speaker": {"Alice": {"tension": 0.4}},
                    }
                }
            }
        },
    )
    out = _aggregate_affect_tension([ok], _speaker_map(), _transcript_set(tmp_path))
    assert out is not None
    assert out["session_rows"][0]["tension"] == 0.3
    assert len(out["speaker_rows"]) == 1

    bad = _result(
        tmp_path,
        {"affect_tension": {"payload": {"derived_indices": "nope"}}},
    )
    warn = _aggregate_affect_tension([bad], _speaker_map(), _transcript_set(tmp_path))
    assert warn is not None
    assert warn["warning"]["aggregation_key"] == "affect_tension"


@pytest.mark.unit
def test_aggregate_qa_loops_temporal_momentum(tmp_path: Path) -> None:
    qa = _result(
        tmp_path,
        {"qa_analysis": {"payload": {"statistics": {"question_count": 5}}}},
    )
    qa_out = _aggregate_qa_analysis([qa], _speaker_map(), _transcript_set(tmp_path))
    assert qa_out is not None
    assert qa_out["session_rows"][0]["question_count"] == 5
    assert qa_out["speaker_rows"] == []

    loops = _result(
        tmp_path,
        {"conversation_loops": {"payload": {"summary": {"loop_count": 2}}}},
    )
    loops_out = _aggregate_conversation_loops(
        [loops], _speaker_map(), _transcript_set(tmp_path)
    )
    assert loops_out is not None
    assert loops_out["session_rows"][0]["loop_count"] == 2

    temporal = _result(
        tmp_path,
        {
            "temporal_dynamics": {
                "payload": {
                    "total_duration": 120.0,
                    "window_size": 30,
                    "num_windows": 4,
                    "phase_detection": {"phases": 2},
                    "ignored": "skip",
                }
            }
        },
    )
    temporal_out = _aggregate_temporal_dynamics(
        [temporal], _speaker_map(), _transcript_set(tmp_path)
    )
    assert temporal_out is not None
    row = temporal_out["session_rows"][0]
    assert row["total_duration"] == 120.0
    assert row["num_windows"] == 4
    assert "ignored" not in row

    mom = _result(
        tmp_path,
        {"momentum": {"payload": {"stats": {"momentum_score": 0.7}}}},
    )
    mom_out = _aggregate_momentum([mom], _speaker_map(), _transcript_set(tmp_path))
    assert mom_out is not None
    assert mom_out["session_rows"][0]["momentum_score"] == 0.7


@pytest.mark.unit
def test_aggregate_contagion_success_blob(tmp_path: Path) -> None:
    result = _result(
        tmp_path,
        {
            "contagion": {
                "payload": {
                    "contagion_summary": {
                        "Alice->Bob": {"joy": 2},
                        "pair_score": 1,
                    },
                    "speaker_emotions": {"Alice": {"joy": 3}},
                }
            }
        },
    )
    out = _aggregate_contagion([result], _speaker_map(), _transcript_set(tmp_path))
    assert out is not None
    assert "session_rows" in out
    assert "contagion_pooled" in out
    assert len(out["speaker_rows"]) == 1


@pytest.mark.unit
def test_aggregate_helpers_return_none_without_payloads(tmp_path: Path) -> None:
    empty = _result(tmp_path, {})
    ts = _transcript_set(tmp_path)
    sm = _speaker_map()
    assert _aggregate_acts([empty], sm, ts) is None
    assert _aggregate_pauses([empty], sm, ts) is None
    assert _aggregate_highlights([empty], sm, ts) is None
    assert _aggregate_momentum([empty], sm, ts) is None
