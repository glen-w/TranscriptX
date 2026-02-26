"""
Contract tests for the emotion analysis module (offline + deterministic).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.emotion import EmotionAnalysis


def _emotion_module_with_mock_model(
    emotion_list: list[dict[str, Any]],
) -> EmotionAnalysis:
    """Create EmotionAnalysis with mocked model and NRC lexicon."""
    mock_model = MagicMock()
    # pipeline(text) returns list of sequences; code uses pipeline(text)[0]
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


class TestEmotionContracts:
    """Contract tests for EmotionAnalysis output shape."""

    @pytest.fixture
    def sample_segments(self) -> list[dict[str, Any]]:
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
        ]

    @pytest.fixture
    def sample_speaker_map(self) -> dict[str, str]:
        """Fixture for sample speaker map (deprecated, kept for backward compatibility)."""
        return {}

    def test_emotion_output_contract(
        self,
        sample_segments: list[dict[str, Any]],
        sample_speaker_map: dict[str, str],
    ) -> None:
        """Assert EmotionAnalysis returns required keys and segment annotations."""
        emotion_module = _emotion_module_with_mock_model(
            [{"label": "joy", "score": 0.9}]
        )
        result = emotion_module.analyze(sample_segments, sample_speaker_map)

        # Top-level keys
        assert "segments_with_emotion" in result
        assert "nrc_scores" in result
        assert "combined_rows" in result
        assert "contextual_all" in result
        assert "contextual_examples" in result
        assert "all_scores" in result
        assert "speaker_stats" in result
        assert "global_stats" in result
        assert "segments" in result
        assert "emotions" in result

        # Types and minimal structure checks
        assert isinstance(result["segments_with_emotion"], list)
        assert isinstance(result["nrc_scores"], dict)
        assert isinstance(result["combined_rows"], list)
        assert isinstance(result["contextual_all"], dict)
        assert isinstance(result["contextual_examples"], dict)
        assert isinstance(result["all_scores"], dict)
        assert isinstance(result["speaker_stats"], dict)
        assert isinstance(result["global_stats"], dict)

        # Segment annotations
        for seg in result["segments_with_emotion"]:
            assert "context_emotion_primary" in seg
            assert "context_emotion_scores" in seg
            assert "context_emotion_source" in seg
