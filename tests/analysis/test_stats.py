"""
Tests for statistical analysis module.

This module tests statistical analysis and metrics calculation.
"""

from __future__ import annotations

from typing import Any

import pytest

from transcriptx.core.analysis.stats import StatsAnalysis  # type: ignore[import-untyped]


class TestStatisticalAnalysisModule:
    """Tests for StatsAnalysis."""

    @pytest.fixture
    def stats_module(self) -> StatsAnalysis:
        """Fixture for StatsAnalysis instance."""
        return StatsAnalysis()

    @pytest.fixture
    def sample_segments(self) -> list[dict[str, Any]]:
        """Fixture for sample transcript segments with segment-based speaker identification."""
        return [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "Hello world",
                "start": 0.0,
                "end": 1.0,
            },
            {
                "speaker": "Bob",
                "speaker_db_id": 2,
                "text": "How are you?",
                "start": 1.0,
                "end": 2.0,
            },
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "I'm fine, thanks!",
                "start": 2.0,
                "end": 3.0,
            },
        ]

    @pytest.fixture
    def sample_speaker_map(self) -> dict[str, str]:
        """Fixture for sample speaker map (deprecated, kept for backward compatibility)."""
        return {}

    def test_stats_analysis_basic(
        self,
        stats_module: StatsAnalysis,
        sample_segments: list[dict[str, Any]],
        sample_speaker_map: dict[str, str],
    ) -> None:
        """Test basic statistical analysis output contract."""
        result = stats_module.analyze(sample_segments)

        assert set(result.keys()) >= {
            "speaker_stats",
            "sentiment_summary",
            "grouped_texts",
            "tic_list",
        }
        assert isinstance(result["grouped_texts"], dict)
        assert set(result["grouped_texts"].keys()) == {"Alice", "Bob"}

    def test_stats_analysis_speaker_stats(
        self,
        stats_module: StatsAnalysis,
        sample_segments: list[dict[str, Any]],
        sample_speaker_map: dict[str, str],
    ) -> None:
        """Test speaker-level statistics."""
        result = stats_module.analyze(sample_segments)

        # Should include speaker statistics
        assert "speaker_stats" in result
        assert isinstance(result["speaker_stats"], list)

    def test_stats_analysis_empty_segments(
        self, stats_module: StatsAnalysis, sample_speaker_map: dict[str, str]
    ) -> None:
        """Test statistical analysis with empty segments."""
        segments: list[dict[str, Any]] = []

        result = stats_module.analyze(segments)

        # Should handle empty segments gracefully
        assert result["grouped_texts"] == {}
        assert result["speaker_stats"] == []

    def test_stats_analysis_falls_back_to_placeholder_speakers(
        self, stats_module: StatsAnalysis, sample_speaker_map: dict[str, str]
    ) -> None:
        """When all speakers are anonymized, stats should still produce totals."""
        segments = [
            {
                "speaker": "SPEAKER_00",
                "text": "Hello there",
                "start": 0.0,
                "end": 1.0,
            },
            {
                "speaker": "SPEAKER_01",
                "text": "General Kenobi",
                "start": 1.0,
                "end": 2.0,
            },
        ]

        result = stats_module.analyze(segments)

        assert set(result["grouped_texts"].keys()) == {"SPEAKER_00", "SPEAKER_01"}
        assert len(result["speaker_stats"]) == 2
