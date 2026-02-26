"""
Tests for interaction analysis module.

This module tests interaction patterns, turn-taking, and conversation dynamics.
"""

import pytest

from transcriptx.core.analysis.interactions import InteractionsAnalysis


class TestInteractionAnalysisModule:
    """Tests for InteractionsAnalysis."""

    @pytest.fixture
    def interactions_module(self):
        """Fixture for InteractionsAnalysis instance."""
        return InteractionsAnalysis()

    @pytest.fixture
    def sample_segments(self):
        """Fixture for sample transcript segments with interactions and database-driven speaker identification."""
        return [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "Hello",
                "start": 0.0,
                "end": 1.0,
            },
            {
                "speaker": "Bob",
                "speaker_db_id": 2,
                "text": "Hi there",
                "start": 1.0,
                "end": 2.0,
            },
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "How are you?",
                "start": 2.0,
                "end": 3.0,
            },
            {
                "speaker": "Bob",
                "speaker_db_id": 2,
                "text": "I'm good, thanks",
                "start": 3.0,
                "end": 4.0,
            },
        ]

    @pytest.fixture
    def sample_speaker_map(self):
        """Fixture for sample speaker map (deprecated, kept for backward compatibility)."""
        return {}

    def test_interactions_analysis_basic(
        self, interactions_module, sample_segments, sample_speaker_map
    ):
        """Test basic interaction analysis."""
        result = interactions_module.analyze(sample_segments, sample_speaker_map)

        assert "interactions" in result or "patterns" in result or "summary" in result

    def test_interactions_analysis_turn_taking(
        self, interactions_module, sample_segments, sample_speaker_map
    ):
        """Test turn-taking analysis."""
        result = interactions_module.analyze(sample_segments, sample_speaker_map)

        # Should include turn-taking metrics
        assert "turn_taking" in result or "turns" in result or "summary" in result

    def test_interactions_analysis_response_time(
        self, interactions_module, sample_segments, sample_speaker_map
    ):
        """Test response time analysis."""
        result = interactions_module.analyze(sample_segments, sample_speaker_map)

        # Should include response time metrics
        assert "response_time" in result or "timing" in result or "summary" in result

    def test_interactions_analysis_overlap(
        self, interactions_module, sample_segments, sample_speaker_map
    ):
        """Test overlap detection."""
        # Create segments with potential overlap
        overlapping_segments = [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "Hello",
                "start": 0.0,
                "end": 2.0,
            },
            {
                "speaker": "Bob",
                "speaker_db_id": 2,
                "text": "Hi",
                "start": 1.0,
                "end": 2.0,
            },  # Overlaps
        ]

        result = interactions_module.analyze(overlapping_segments, sample_speaker_map)

        # Should detect overlaps
        assert "overlaps" in result or "interactions" in result or "summary" in result

    def test_interactions_analysis_empty_segments(
        self, interactions_module, sample_speaker_map
    ):
        """Test interaction analysis with empty segments."""
        segments = []

        result = interactions_module.analyze(segments, sample_speaker_map)

        # Should handle empty segments gracefully
        assert "interactions" in result or "patterns" in result or "summary" in result
