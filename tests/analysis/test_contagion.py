"""
Tests for emotional contagion analysis module.

This module tests emotional contagion detection between speakers.
"""

import pytest

from transcriptx.core.analysis.contagion import ContagionAnalysis


class TestContagionAnalysis:
    """Tests for ContagionAnalysis."""

    @pytest.fixture
    def contagion_module(self):
        """Fixture for ContagionAnalysis instance."""
        return ContagionAnalysis()

    @pytest.fixture
    def sample_segments_with_emotion(self):
        """Fixture for sample transcript segments with emotion data using database-driven speaker identification."""
        return [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "I'm so happy about this!",
                "start": 0.0,
                "end": 2.0,
                "context_emotion": {"joy": 0.9, "sadness": 0.1},
            },
            {
                "speaker": "Bob",
                "speaker_db_id": 2,
                "text": "That's great! I'm happy too!",
                "start": 2.0,
                "end": 4.0,
                "context_emotion": {"joy": 0.8, "sadness": 0.2},
            },
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "This is wonderful news.",
                "start": 4.0,
                "end": 6.0,
                "context_emotion": {"joy": 0.7, "sadness": 0.3},
            },
        ]

    @pytest.fixture
    def sample_segments_no_emotion(self):
        """Fixture for sample transcript segments without emotion data using database-driven speaker identification."""
        return [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "Hello there.",
                "start": 0.0,
                "end": 2.0,
            },
            {
                "speaker": "Bob",
                "speaker_db_id": 2,
                "text": "Hi!",
                "start": 2.0,
                "end": 4.0,
            },
        ]

    @pytest.fixture
    def sample_speaker_map(self):
        """Fixture for sample speaker map (deprecated, kept for backward compatibility)."""
        return {}

    def test_contagion_analysis_with_emotion_data(
        self, contagion_module, sample_segments_with_emotion, sample_speaker_map
    ):
        """Test contagion analysis with emotion data in segments."""
        result = contagion_module.analyze(
            sample_segments_with_emotion, sample_speaker_map
        )

        assert (
            "contagion_events" in result
            or "contagion_analysis" in result
            or "summary" in result
        )
        assert "segments" in result or "timeline" in result

    def test_contagion_analysis_no_emotion_data(
        self, contagion_module, sample_segments_no_emotion, sample_speaker_map
    ):
        """Test contagion analysis without emotion data raises error."""
        with pytest.raises(ValueError, match="No emotion data found"):
            contagion_module.analyze(sample_segments_no_emotion, sample_speaker_map)

    def test_contagion_analysis_with_emotion_parameter(
        self, contagion_module, sample_segments_no_emotion, sample_speaker_map
    ):
        """Test contagion analysis with emotion data as parameter."""
        emotion_data = {
            "segments_with_emotion": [
                {"context_emotion": {"joy": 0.9, "sadness": 0.1}},
                {"context_emotion": {"joy": 0.8, "sadness": 0.2}},
            ]
        }

        result = contagion_module.analyze(
            sample_segments_no_emotion, sample_speaker_map, emotion_data=emotion_data
        )

        assert result is not None
        assert (
            "contagion_events" in result
            or "contagion_analysis" in result
            or "summary" in result
        )

    def test_contagion_analysis_nrc_emotion(self, contagion_module, sample_speaker_map):
        """Test contagion analysis with NRC emotion data."""
        segments = [
            {
                "speaker": "SPEAKER_00",
                "text": "I'm excited!",
                "start": 0.0,
                "end": 2.0,
                "nrc_emotion": {"joy": 0.9, "fear": 0.1},
            },
            {
                "speaker": "SPEAKER_01",
                "text": "Me too!",
                "start": 2.0,
                "end": 4.0,
                "nrc_emotion": {"joy": 0.8, "fear": 0.2},
            },
        ]

        result = contagion_module.analyze(segments, sample_speaker_map)

        assert result is not None
        assert (
            "contagion_events" in result
            or "contagion_analysis" in result
            or "summary" in result
        )

    def test_contagion_analysis_empty_segments(
        self, contagion_module, sample_speaker_map
    ):
        """Test contagion analysis with empty segments."""
        segments = []

        with pytest.raises(ValueError, match="No emotion data found"):
            contagion_module.analyze(segments, sample_speaker_map)

    def test_contagion_analysis_single_speaker(
        self, contagion_module, sample_speaker_map
    ):
        """Test contagion analysis with single speaker (should handle gracefully)."""
        segments = [
            {
                "speaker": "SPEAKER_00",
                "text": "I'm happy.",
                "start": 0.0,
                "end": 2.0,
                "context_emotion": {"joy": 0.9},
            },
            {
                "speaker": "SPEAKER_00",
                "text": "Still happy.",
                "start": 2.0,
                "end": 4.0,
                "context_emotion": {"joy": 0.8},
            },
        ]

        result = contagion_module.analyze(segments, sample_speaker_map)

        # Should handle single speaker (may not detect contagion but shouldn't crash)
        assert result is not None
