"""
Tests for lexical emotion detection (NRCLex vocabulary association).

EmotionAnalysis no longer loads HF classifiers or writes context_emotion_*.
Projections are deferred until canonical persist.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from transcriptx.core.analysis.emotion import EmotionAnalysis
from transcriptx.core.analysis.emotion.lexical_pipeline import PLUTCHIK_EIGHT
from transcriptx.core.analysis.emotion.projections import apply_lexical_projection
from transcriptx.core.analysis.emotion_family.persist import apply_pending_projections


@pytest.mark.unit
class TestEmotionAnalysisModule:
    """Tests for EmotionAnalysis (lexical v2)."""

    @pytest.fixture
    def sample_segments(self):
        return [
            {
                "id": "1",
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "I'm so happy about this!",
                "start": 0.0,
                "end": 2.0,
            },
            {
                "id": "2",
                "speaker": "Bob",
                "speaker_db_id": 2,
                "text": "This makes me angry.",
                "start": 2.0,
                "end": 4.0,
            },
            {
                "id": "3",
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "I feel sad about the situation.",
                "start": 4.0,
                "end": 6.0,
            },
        ]

    def test_emotion_analysis_basic(self, sample_segments):
        pytest.importorskip("nrclex")
        emotion_module = EmotionAnalysis()
        result = emotion_module.analyze(sample_segments)
        assert result.get("usable_output") is True
        assert result.get("_pending_projections")
        assert "nrc_emotion" not in sample_segments[0]
        apply_pending_projections(result, apply_one=apply_lexical_projection)
        for seg in sample_segments:
            assert "nrc_emotion" in seg
            assert "emotion_evaluation_state" in seg
            assert "context_emotion_primary" not in seg
            assert set(seg["nrc_emotion"]).issubset(set(PLUTCHIK_EIGHT)) or set(
                PLUTCHIK_EIGHT
            ).issubset(set(seg["nrc_emotion"]))

    def test_emotion_analysis_happy_text(self):
        pytest.importorskip("nrclex")
        segments = [
            {
                "id": "1",
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "I'm so happy and joyful and love this!",
                "start": 0.0,
                "end": 2.0,
            }
        ]
        result = EmotionAnalysis().analyze(segments)
        assert result.get("usable_output") is True
        apply_pending_projections(result, apply_one=apply_lexical_projection)
        assert segments[0]["nrc_emotion"].get("joy", 0) > 0
        assert "context_emotion_primary" not in segments[0]

    def test_emotion_analysis_angry_text(self):
        pytest.importorskip("nrclex")
        segments = [
            {
                "id": "1",
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "This is hate and anger and rage!",
                "start": 0.0,
                "end": 2.0,
            }
        ]
        result = EmotionAnalysis().analyze(segments)
        assert result.get("usable_output") is True
        apply_pending_projections(result, apply_one=apply_lexical_projection)
        assert "nrc_emotion" in segments[0]

    def test_emotion_analysis_sad_text(self):
        pytest.importorskip("nrclex")
        segments = [
            {
                "id": "1",
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "I feel really sad and lonely about this.",
                "start": 0.0,
                "end": 2.0,
            }
        ]
        result = EmotionAnalysis().analyze(segments)
        assert result.get("usable_output") is True
        apply_pending_projections(result, apply_one=apply_lexical_projection)
        assert segments[0]["nrc_emotion"].get("sadness", 0) > 0

    def test_emotion_analysis_empty_segments(self):
        pytest.importorskip("nrclex")
        result = EmotionAnalysis().analyze([])
        assert result.get("run_status") in {"complete", "empty", "skipped", "failed"}
        assert int(result.get("segments_scored") or 0) == 0
        assert result.get("ordered_segment_ids") == []

    def test_projections_apply_only_after_persist(self, tmp_path, sample_segments):
        pytest.importorskip("nrclex")
        mod = EmotionAnalysis()
        result = mod.analyze(sample_segments)
        assert "nrc_emotion" not in sample_segments[0]
        output = MagicMock()
        output.get_output_structure.return_value = MagicMock(module_dir=tmp_path)
        mod._save_results(result, output)
        assert "nrc_emotion" in sample_segments[0]
        assert result.get("enriched_projection_status") == "ok"
