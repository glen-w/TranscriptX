"""Contract tests for transcript_quality ASR confidence payload."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.transcript_quality.analyze import (
    SCHEMA_VERSION,
    compute_asr_confidence,
)
from transcriptx.core.analysis.transcript_quality.spans import SpanBuildConfig

pytestmark = pytest.mark.contract


def _scored_segments():
    return [
        {
            "start": 0.0,
            "end": 1.0,
            "speaker": "A",
            "text": "hello world",
            "words": [
                {
                    "word": "hello",
                    "start": 0.0,
                    "end": 0.4,
                    "score": 0.2,
                    "speaker": "A",
                },
                {
                    "word": "world",
                    "start": 0.4,
                    "end": 1.0,
                    "score": 0.9,
                    "speaker": "A",
                },
            ],
        }
    ]


def test_asr_confidence_contract_keys_and_playback() -> None:
    payload = compute_asr_confidence(_scored_segments(), cfg=SpanBuildConfig())
    assert payload["schema_version"] == SCHEMA_VERSION
    assert "disclaimer" in payload
    assert "provenance" in payload
    assert "comparable_key" in payload["provenance"]
    asr = payload["asr_confidence"]
    for key in (
        "status",
        "eligible_word_count",
        "scored_word_count",
        "coverage_ratio",
        "missing_score_count",
        "invalid_score_count",
        "out_of_range_score_count",
        "excluded_unusable_count",
        "spans_total_count",
        "spans_emitted_count",
        "clusters_total_count",
        "clusters_emitted_count",
        "spans",
        "clusters",
    ):
        assert key in asr
    assert asr["status"] == "partial" or asr["status"] == "present"
    assert asr["spans"]
    play = asr["spans"][0]["playback"]
    assert play is not None
    assert {"start", "end", "segment_index"} <= set(play)
    assert "filler" not in payload
    assert "quality_score" not in payload
    assert "overall_quality" not in asr


def test_absent_contract_has_empty_spans() -> None:
    segs = [
        {
            "start": 0.0,
            "end": 1.0,
            "speaker": "A",
            "text": "hello",
            "words": [{"word": "hello", "start": 0.0, "end": 1.0, "speaker": "A"}],
        }
    ]
    asr = compute_asr_confidence(segs, cfg=SpanBuildConfig())["asr_confidence"]
    assert asr["status"] == "absent"
    assert asr["spans"] == []
    assert asr["clusters"] == []
    assert asr["scored_word_count"] == 0
    assert asr["coverage_ratio"] == 0.0  # eligible words present, none scored
