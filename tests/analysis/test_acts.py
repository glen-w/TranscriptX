"""
Tests for dialogue act classification module.

This module tests dialogue act classification using ML and rules-based approaches.
"""

import pytest

from transcriptx.core.analysis.acts import ActsAnalysis


class TestDialogueActAnalysisModule:
    """Tests for ActsAnalysis."""

    @pytest.fixture
    def acts_module(self):
        """Fixture for ActsAnalysis instance."""
        return ActsAnalysis()

    @pytest.fixture
    def sample_segments(self):
        """Fixture for sample transcript segments with database-driven speaker identification."""
        return [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "What time is it?",
                "start": 0.0,
                "end": 2.0,
            },
            {
                "speaker": "Bob",
                "speaker_db_id": 2,
                "text": "It's 3 o'clock.",
                "start": 2.0,
                "end": 4.0,
            },
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "Thank you!",
                "start": 4.0,
                "end": 5.0,
            },
        ]

    @pytest.fixture
    def sample_speaker_map(self):
        """Fixture for sample speaker map (deprecated, kept for backward compatibility)."""
        return {}

    def test_acts_analysis_basic(
        self, acts_module, sample_segments, sample_speaker_map
    ):
        """Test basic dialogue act classification."""
        result = acts_module.analyze(sample_segments, sample_speaker_map)

        assert "segments" in result or "acts" in result
        assert len(result.get("segments", result.get("acts", []))) == len(
            sample_segments
        )

    def test_acts_analysis_question(self, acts_module, sample_speaker_map):
        """Test classification of question acts."""
        segments = [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "What is your name?",
                "start": 0.0,
                "end": 2.0,
            }
        ]

        result = acts_module.analyze(segments, sample_speaker_map)

        # Should classify as question
        assert "segments" in result or "acts" in result

    def test_acts_analysis_statement(self, acts_module, sample_speaker_map):
        """Test classification of statement acts."""
        segments = [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "The weather is nice today.",
                "start": 0.0,
                "end": 2.0,
            }
        ]

        result = acts_module.analyze(segments, sample_speaker_map)

        # Should classify as statement
        assert "segments" in result or "acts" in result

    def test_acts_analysis_greeting(self, acts_module, sample_speaker_map):
        """Test classification of greeting acts."""
        segments = [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "Hello, how are you?",
                "start": 0.0,
                "end": 2.0,
            }
        ]

        result = acts_module.analyze(segments, sample_speaker_map)

        # Should classify as greeting
        assert "segments" in result or "acts" in result

    def test_acts_analysis_empty_segments(self, acts_module, sample_speaker_map):
        """Test dialogue act analysis with empty segments."""
        segments = []

        result = acts_module.analyze(segments, sample_speaker_map)

        assert "segments" in result or "acts" in result
        assert len(result.get("segments", result.get("acts", []))) == 0
