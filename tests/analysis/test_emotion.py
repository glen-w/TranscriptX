"""
Tests for emotion detection module.

This module tests emotion detection and transformer model integration.
Emotion module uses get_transformers().pipeline() via _load_emotion_model.
"""

from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.emotion import EmotionAnalysis


def _emotion_module_with_mock_model(emotion_list):
    """Create EmotionAnalysis with mocked _load_emotion_model. emotion_list is the list of label/score dicts; pipeline(text)[0] is used."""
    mock_model = MagicMock()
    # pipeline(text) returns list of sequences; code uses pipeline(text)[0] -> one sequence of label/score dicts
    mock_model.return_value = [emotion_list]
    cfg = MagicMock()
    cfg.analysis.emotion_model_name = "test/model"
    cfg.analysis.emotion_output_mode = "top1"
    cfg.analysis.emotion_score_threshold = 0.30
    with patch("transcriptx.core.utils.config.get_config", return_value=cfg):
        with patch("transcriptx.core.analysis.emotion._load_nrclex", return_value=None):
            with patch(
                "transcriptx.core.analysis.emotion._load_emotion_model",
                return_value=mock_model,
            ):
                return EmotionAnalysis()


class TestEmotionAnalysisModule:
    """Tests for EmotionAnalysis."""

    @pytest.fixture
    def sample_segments(self):
        """Fixture for sample transcript segments with database-driven speaker identification."""
        return [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "I'm so happy about this!",
                "start": 0.0,
                "end": 2.0,
            },
            {
                "speaker": "Bob",
                "speaker_db_id": 2,
                "text": "This makes me angry.",
                "start": 2.0,
                "end": 4.0,
            },
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "I feel sad about the situation.",
                "start": 4.0,
                "end": 6.0,
            },
        ]

    @pytest.fixture
    def sample_speaker_map(self):
        """Fixture for sample speaker map (deprecated, kept for backward compatibility)."""
        return {}

    def test_emotion_analysis_basic(self, sample_segments, sample_speaker_map):
        """Test basic emotion detection."""
        emotion_module = _emotion_module_with_mock_model(
            [{"label": "joy", "score": 0.9}]
        )
        result = emotion_module.analyze(sample_segments, sample_speaker_map)
        assert "segments" in result or "emotions" in result
        # New contract: segments have context_emotion_primary, context_emotion_scores, context_emotion_source
        for seg in sample_segments:
            assert "context_emotion_primary" in seg
            assert "context_emotion_scores" in seg
            assert seg.get("context_emotion") == seg.get(
                "context_emotion_primary"
            )  # backward compat

    def test_emotion_analysis_happy_text(self, sample_speaker_map):
        """Test emotion detection on happy text."""
        segments = [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "I'm so happy and excited!",
                "start": 0.0,
                "end": 2.0,
            }
        ]
        emotion_module = _emotion_module_with_mock_model(
            [{"label": "joy", "score": 0.95}]
        )
        result = emotion_module.analyze(segments, sample_speaker_map)
        assert "segments" in result or "emotions" in result
        assert segments[0].get("context_emotion_primary") == "joy"

    def test_emotion_analysis_angry_text(self, sample_speaker_map):
        """Test emotion detection on angry text."""
        segments = [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "This is infuriating!",
                "start": 0.0,
                "end": 2.0,
            }
        ]
        emotion_module = _emotion_module_with_mock_model(
            [{"label": "anger", "score": 0.9}]
        )
        result = emotion_module.analyze(segments, sample_speaker_map)
        assert "segments" in result or "emotions" in result
        assert segments[0].get("context_emotion_primary") == "anger"

    def test_emotion_analysis_sad_text(self, sample_speaker_map):
        """Test emotion detection on sad text."""
        segments = [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "I feel really sad about this.",
                "start": 0.0,
                "end": 2.0,
            }
        ]
        emotion_module = _emotion_module_with_mock_model(
            [{"label": "sadness", "score": 0.85}]
        )
        result = emotion_module.analyze(segments, sample_speaker_map)
        assert "segments" in result or "emotions" in result
        assert segments[0].get("context_emotion_primary") == "sadness"

    def test_emotion_analysis_empty_segments(self, sample_speaker_map):
        """Test emotion analysis with empty segments."""
        emotion_module = _emotion_module_with_mock_model(
            [{"label": "joy", "score": 0.9}]
        )
        segments = []
        result = emotion_module.analyze(segments, sample_speaker_map)
        assert "segments" in result or "emotions" in result
        assert (
            len(result.get("segments", [])) == 0 or len(result.get("emotions", [])) == 0
        )
