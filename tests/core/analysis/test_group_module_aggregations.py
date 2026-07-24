"""Unit tests for new group aggregation modules (LLM, insights, semantic, voice)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.analysis.aggregation.insights import aggregate_insights_group
from transcriptx.core.analysis.aggregation.llm import (
    aggregate_llm_action_items_group,
    aggregate_llm_speaker_summary_group,
    aggregate_llm_summary_blob,
    aggregate_narrative_summary_blob,
)
from transcriptx.core.analysis.aggregation.semantic_similarity import (
    aggregate_semantic_similarity_group,
)
from transcriptx.core.analysis.aggregation.voice import (
    aggregate_voice_fingerprint_group,
    aggregate_voice_mismatch_group,
    aggregate_voice_tension_group,
)
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


def _result(
    path: str,
    key: str,
    order: int,
    module_results: dict,
    output_dir: str = "o1",
) -> PerTranscriptResult:
    return PerTranscriptResult(
        transcript_path=path,
        transcript_key=key,
        run_id=f"r{order}",
        order_index=order,
        output_dir=output_dir,
        module_results=module_results,
    )


@pytest.mark.unit
def test_aggregate_llm_summary_blob_collects_summaries() -> None:
    results = [
        _result(
            "/x/a.json",
            "a",
            0,
            {"llm_summary": {"payload": {"summary": "One", "provenance": {}}}},
        ),
        _result(
            "/x/b.json",
            "b",
            1,
            {"llm_summary": {"payload": {"summary": "Two", "provenance": {}}}},
            output_dir="o2",
        ),
    ]
    out = aggregate_llm_summary_blob(results, _cmap(), _ts())
    assert out is not None
    assert out["blob_name"] == "llm_summary"
    summaries = out["blob_payload"]["summaries"]
    assert [row["summary"] for row in summaries] == ["One", "Two"]
    assert summaries[0]["source_transcript_id"]
    assert summaries[0]["order_index"] == 0


@pytest.mark.unit
def test_aggregate_narrative_summary_blob_none_when_empty() -> None:
    assert aggregate_narrative_summary_blob([], _cmap(), _ts()) is None


@pytest.mark.unit
def test_aggregate_llm_action_items_dedupes_across_sessions() -> None:
    item = {
        "record_type": "action_item",
        "text": "Ship it",
        "owner": "Alice",
        "deadline": None,
        "status": "open",
        "quote": "ship it",
        "confidence": 0.9,
    }

    def _payload(items: list) -> dict:
        return {
            "schema_id": "transcriptx.llm_action_items.v1",
            "module_version": "2",
            "items": items,
        }

    results = [
        _result(
            "/x/a.json",
            "a",
            0,
            {"llm_action_items": {"payload": _payload([item])}},
        ),
        _result(
            "/x/b.json",
            "b",
            1,
            {
                "llm_action_items": {
                    "payload": _payload(
                        [
                            {**item, "confidence": 0.5, "quote": None},
                            {
                                "record_type": "action_item",
                                "text": "Other",
                                "owner": None,
                                "deadline": None,
                                "status": "done",
                                "quote": None,
                                "confidence": 0.4,
                            },
                        ]
                    )
                }
            },
            output_dir="o2",
        ),
    ]
    out = aggregate_llm_action_items_group(results, _cmap(), _ts())
    assert out is not None
    assert out["schema_version"] == 2
    assert out["session_rows"][0]["item_count"] == 1
    assert out["session_rows"][1]["item_count"] == 2
    texts = [row["text"] for row in out["content_rows"]]
    assert texts.count("Ship it") == 1
    assert "Other" in texts


@pytest.mark.unit
def test_aggregate_llm_speaker_summary_loads_artifacts(tmp_path: Path) -> None:
    speakers_dir = tmp_path / "llm_speaker_summary" / "data" / "speakers"
    speakers_dir.mkdir(parents=True)
    transcript = tmp_path / "a.json"
    transcript.write_text("{}", encoding="utf-8")
    (speakers_dir / "a_Alice_llm_speaker_summary.json").write_text(
        json.dumps({"summary": "Alice spoke clearly"}),
        encoding="utf-8",
    )
    results = [
        _result(
            str(transcript),
            "a",
            0,
            {
                "llm_speaker_summary": {
                    "payload": {
                        "speakers": [
                            {
                                "speaker": "Alice",
                                "speaker_key": "1",
                                "status": "success",
                                "artifact_stem": "llm_speaker_summary",
                            }
                        ]
                    }
                }
            },
            output_dir=str(tmp_path),
        )
    ]
    cmap = CanonicalSpeakerMap(
        transcript_to_speakers={str(transcript): {"1": 7}},
        canonical_to_display={7: "Alice"},
        transcript_to_display={str(transcript): {"1": "Alice"}},
    )
    ts = TranscriptSet.create([str(transcript)], name="G", key="gk")
    out = aggregate_llm_speaker_summary_group(results, cmap, ts)
    assert out is not None
    assert out["speaker_rows"][0]["summary"] == "Alice spoke clearly"
    assert out["session_rows"][0]["success_count"] == 1


@pytest.mark.unit
def test_aggregate_insights_group_builds_content_rows() -> None:
    results = [
        _result(
            "/x/a.json",
            "a",
            0,
            {
                "insights": {
                    "payload": {
                        "key_themes": [{"phrase": "roadmap", "score": {"total": 2.0}}],
                        "recurring_ideas": [
                            {"phrase": "timeline", "score": {"total": 1.5}}
                        ],
                        "notable_moments": [
                            {"quote": "We must ship", "start": 1.0, "end": 2.0}
                        ],
                    }
                }
            },
        )
    ]
    out = aggregate_insights_group(results, _cmap(), _ts())
    assert out is not None
    assert out["session_rows"][0]["theme_count"] == 1
    kinds = {row["kind"] for row in out["content_rows"]}
    assert kinds == {"key_theme", "recurring_idea", "notable_moment"}


@pytest.mark.unit
def test_aggregate_highlights_partial_member_payloads() -> None:
    from transcriptx.core.analysis.aggregation.registry import _aggregate_highlights

    results = [
        _result("/x/a.json", "a", 0, {}),
        _result(
            "/x/b.json",
            "b",
            1,
            {
                "highlights": {
                    "payload": {
                        "sections": {
                            "cold_open": {
                                "items": [
                                    {
                                        "speaker": "Alice",
                                        "start": 0.0,
                                        "end": 1.0,
                                        "quote": "Hello from B",
                                        "score": {"total": 0.9},
                                    }
                                ]
                            }
                        }
                    }
                }
            },
            output_dir="o2",
        ),
    ]
    out = _aggregate_highlights(results, _cmap(), _ts())
    assert out is not None
    assert len(out["content_rows"]) == 1
    assert out["content_rows"][0]["text"] == "Hello from B"
    assert out["content_rows"][0]["order_index"] == 1

    """Partial member success: only members with insights contribute rows."""
    results = [
        _result("/x/a.json", "a", 0, {}),  # skipped / missing insights
        _result(
            "/x/b.json",
            "b",
            1,
            {
                "insights": {
                    "payload": {
                        "key_themes": [{"phrase": "only-b", "score": {"total": 1.0}}],
                        "recurring_ideas": [],
                        "notable_moments": [],
                    }
                }
            },
            output_dir="o2",
        ),
    ]
    out = aggregate_insights_group(results, _cmap(), _ts())
    assert out is not None
    assert len(out["session_rows"]) == 1
    assert out["session_rows"][0]["order_index"] == 1
    assert out["content_rows"][0]["text"] == "only-b"


@pytest.mark.unit
def test_aggregate_llm_summary_blob_skips_empty_members() -> None:
    results = [
        _result("/x/a.json", "a", 0, {"llm_summary": {"payload": {}}}),
        _result(
            "/x/b.json",
            "b",
            1,
            {"llm_summary": {"payload": {"summary": "Only B"}}},
            output_dir="o2",
        ),
    ]
    out = aggregate_llm_summary_blob(results, _cmap(), _ts())
    assert out is not None
    summaries = out["blob_payload"]["summaries"]
    assert len(summaries) == 1
    assert summaries[0]["summary"] == "Only B"


@pytest.mark.unit
def test_aggregate_semantic_similarity_prefers_v2() -> None:
    results = [
        _result(
            "/x/a.json",
            "a",
            0,
            {
                "semantic_similarity": {
                    "payload": {"total_repetitions": 1, "unique_patterns": 1}
                },
                "semantic_similarity": {
                    "payload": {
                        "total_repetitions": 3,
                        "unique_patterns": 2,
                        "mode": "fast",
                        "speaker_repetitions": {
                            "Alice": [
                                {
                                    "segment1": {
                                        "speaker": "Alice",
                                        "text": "hello",
                                    },
                                    "segment2": {
                                        "speaker": "Alice",
                                        "text": "hi",
                                    },
                                    "similarity": 0.91,
                                    "type": "self",
                                }
                            ]
                        },
                        "cross_speaker_repetitions": [],
                    }
                },
            },
        )
    ]
    out = aggregate_semantic_similarity_group(results, _cmap(), _ts())
    assert out is not None
    assert out["session_rows"][0]["total_repetitions"] == 3
    assert out["session_rows"][0]["semantic_module"] == "semantic_similarity"
    assert len(out["content_rows"]) == 1
    assert out["content_rows"][0]["similarity"] == 0.91


@pytest.mark.unit
def test_aggregate_voice_mismatch_and_tension() -> None:
    mismatch = aggregate_voice_mismatch_group(
        [
            _result(
                "/x/a.json",
                "a",
                0,
                {
                    "voice_mismatch": {
                        "payload": {
                            "summary": {"moments_count": 1},
                            "moments": [
                                {
                                    "start_s": 1.0,
                                    "end_s": 2.0,
                                    "speaker": "Alice",
                                    "text": "fine",
                                    "mismatch_score": 0.8,
                                }
                            ],
                        }
                    }
                },
            )
        ],
        _cmap(),
        _ts(),
    )
    assert mismatch is not None
    assert mismatch["session_rows"][0]["moments_count"] == 1
    assert mismatch["content_rows"][0]["score"] == 0.8

    tension = aggregate_voice_tension_group(
        [
            _result(
                "/x/a.json",
                "a",
                0,
                {
                    "voice_tension": {
                        "payload": {
                            "summary": {"bins": 2, "bin_seconds": 5.0},
                            "curve": [
                                {"start_s": 0.0, "tension": 0.2},
                                {"start_s": 5.0, "tension": 0.6},
                            ],
                        }
                    }
                },
            )
        ],
        _cmap(),
        _ts(),
    )
    assert tension is not None
    assert tension["session_rows"][0]["tension_max"] == 0.6
    assert len(tension["content_rows"]) == 2


@pytest.mark.unit
def test_aggregate_voice_fingerprint_speaker_rows() -> None:
    out = aggregate_voice_fingerprint_group(
        [
            _result(
                "/x/a.json",
                "a",
                0,
                {
                    "voice_fingerprint": {
                        "payload": {
                            "summary": {"speakers": 1},
                            "fingerprints": {
                                "Alice": {
                                    "n_segments": 4,
                                    "baseline": {
                                        "rms_db": {"median": -20.0},
                                        "f0_range_semitones": {"median": 3.0},
                                        "speech_rate_wps": {"median": 2.5},
                                    },
                                }
                            },
                            "drift_moments": {
                                "Alice": [
                                    {
                                        "start_s": 1.0,
                                        "end_s": 2.0,
                                        "drift_score": 2.2,
                                        "text": "loud",
                                    }
                                ]
                            },
                        }
                    }
                },
            )
        ],
        _cmap(),
        _ts(),
    )
    assert out is not None
    assert out["speaker_rows"][0]["rms_db_median"] == -20.0
    assert out["content_rows"][0]["score"] == 2.2
