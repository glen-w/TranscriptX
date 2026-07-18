"""
Tests for emotional contagion analysis module.

Frozen branch contract: lexical branch from nrc_emotion; contextual branch
only via a satisfied contextual_emotion producer contract (schema v2).
"""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.contagion import ContagionAnalysis
from transcriptx.core.analysis.emotion_family.fingerprints import segment_text_hash

pytestmark = pytest.mark.unit


def _contextual_artifact(segments):
    return {
        "schema_version": "contextual_emotion_result_schema_v2",
        "semantics_version": "contextual_emotion_v1",
        "module_id": "contextual_emotion",
        "run_status": "complete",
        "usable_output": True,
        "segments_scored": len(segments),
        "artifact_generation_id": "a" * 32,
        "projection_fields": [
            "segment_id",
            "evaluation_state",
            "analytical_outcome",
            "contextual_emotion_label",
            "contextual_emotion_confidence",
            "truncated",
            "canonical_ref",
        ],
        "segments_with_contextual_emotion": segments,
    }


def _contextual_seg(sid: str, speaker: str, text: str, *, db_id: int, start: float):
    return {
        "id": sid,
        "speaker": speaker,
        "speaker_db_id": db_id,
        "text": text,
        "start": start,
        "end": start + 2.0,
        "context_emotion": "joy",
        "context_emotion_primary": "joy",
        "context_emotion_source": "contextual_emotion",
        "contextual_emotion_label": "joy",
        "contextual_emotion_confidence": 0.9,
        "contextual_emotion_analytical_outcome": "labeled",
        "contextual_emotion_scored_text_hash": segment_text_hash(text),
    }


class TestContagionAnalysis:
    """Tests for ContagionAnalysis."""

    @pytest.fixture
    def contagion_module(self):
        return ContagionAnalysis()

    @pytest.fixture
    def sample_segments_contextual(self):
        return [
            _contextual_seg(
                "1", "Alice", "I'm so happy about this!", db_id=1, start=0.0
            ),
            _contextual_seg(
                "2", "Bob", "That's great! I'm happy too!", db_id=2, start=2.0
            ),
            _contextual_seg(
                "3", "Alice", "This is wonderful news.", db_id=1, start=4.0
            ),
        ]

    @pytest.fixture
    def sample_segments_no_emotion(self):
        return [
            {
                "id": "1",
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "Hello there.",
                "start": 0.0,
                "end": 2.0,
            },
            {
                "id": "2",
                "speaker": "Bob",
                "speaker_db_id": 2,
                "text": "Hi!",
                "start": 2.0,
                "end": 4.0,
            },
        ]

    def test_contagion_analysis_with_contextual_producer(
        self, contagion_module, sample_segments_contextual
    ):
        result = contagion_module.analyze(
            sample_segments_contextual,
            contextual_emotion_data=_contextual_artifact(sample_segments_contextual),
        )

        assert "contagion_events" in result
        assert result["run_status"] == "complete"
        assert result["emotion_type"] == "context_emotion"
        assert "contextual_emotion" in result["branches"]
        assert "timeline" in result
        assert isinstance(result["contagion_counts"], list)

    def test_contagion_analysis_no_emotion_data(
        self, contagion_module, sample_segments_no_emotion
    ):
        result = contagion_module.analyze(sample_segments_no_emotion)
        assert result["run_status"] == "not_applicable"
        assert result["usable_output"] is False
        assert result["contagion_events"] == []
        assert result["contagion_counts"] == []

    def test_contagion_analysis_legacy_context_fields_rejected(
        self, contagion_module, sample_segments_no_emotion
    ):
        legacy = [
            {**seg, "context_emotion": {"joy": 0.9, "sadness": 0.1}}
            for seg in sample_segments_no_emotion
        ]
        result = contagion_module.analyze(legacy)
        assert result["run_status"] == "not_applicable"
        assert result["usable_output"] is False

    def test_contagion_analysis_nrc_emotion(self, contagion_module):
        segments = [
            {
                "id": "1",
                "speaker": "SPEAKER_00",
                "text": "I'm excited!",
                "start": 0.0,
                "end": 2.0,
                "nrc_emotion": {"joy": 0.9, "fear": 0.1},
                "emotion_evaluation_state": "scored",
            },
            {
                "id": "2",
                "speaker": "SPEAKER_01",
                "text": "Me too!",
                "start": 2.0,
                "end": 4.0,
                "nrc_emotion": {"joy": 0.8, "fear": 0.2},
                "emotion_evaluation_state": "scored",
            },
        ]

        result = contagion_module.analyze(segments)

        assert result is not None
        assert result["emotion_type"] == "nrc_emotion"
        assert "contagion_events" in result
        assert isinstance(result["contagion_counts"], list)

    def test_contagion_analysis_empty_segments(self, contagion_module):
        result = contagion_module.analyze([])
        assert result["run_status"] == "not_applicable"
        assert result["usable_output"] is False
        assert result["contagion_counts"] == []

    def test_contagion_analysis_single_speaker(self, contagion_module):
        segments = [
            {
                "id": "1",
                "speaker": "SPEAKER_00",
                "text": "I'm happy.",
                "start": 0.0,
                "end": 2.0,
                "nrc_emotion": {"joy": 0.9},
                "emotion_evaluation_state": "scored",
            },
            {
                "id": "2",
                "speaker": "SPEAKER_00",
                "text": "Still happy.",
                "start": 2.0,
                "end": 4.0,
                "nrc_emotion": {"joy": 0.8},
                "emotion_evaluation_state": "scored",
            },
        ]

        result = contagion_module.analyze(segments)
        assert result is not None
        assert result["run_status"] == "complete"
