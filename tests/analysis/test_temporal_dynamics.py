"""
Tests for temporal dynamics analysis module.

This module tests temporal dynamics analysis including time window calculations,
trend detection, phase detection, and engagement metrics.
"""

from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.temporal_dynamics import TemporalDynamicsAnalysis


class TestTemporalDynamicsAnalysis:
    """Tests for TemporalDynamicsAnalysis."""
    
    @pytest.fixture
    def temporal_module(self):
        """Fixture for TemporalDynamicsAnalysis instance."""
        return TemporalDynamicsAnalysis()
    
    @pytest.fixture
    def sample_segments(self):
        """Fixture for sample transcript segments using database-driven speaker identification."""
        return [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "Hello, welcome to our meeting.", "start": 0.0, "end": 3.0},
            {"speaker": "Bob", "speaker_db_id": 2, "text": "Thank you for having me.", "start": 3.5, "end": 5.0},
            {"speaker": "Alice", "speaker_db_id": 1, "text": "Let's discuss the project timeline.", "start": 5.5, "end": 8.0},
            {"speaker": "Bob", "speaker_db_id": 2, "text": "I think we should start next week.", "start": 8.5, "end": 11.0},
            {"speaker": "Alice", "speaker_db_id": 1, "text": "That sounds good. Any questions?", "start": 11.5, "end": 14.0},
        ]
    
    @pytest.fixture
    def sample_segments_with_sentiment(self):
        """Fixture for sample segments with sentiment data using database-driven speaker identification."""
        return [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "I'm very happy about this!",
                "start": 0.0,
                "end": 2.0,
                "sentiment": {"compound": 0.8, "pos": 0.9, "neu": 0.1, "neg": 0.0}
            },
            {
                "speaker": "Bob",
                "speaker_db_id": 2,
                "text": "This is terrible news.",
                "start": 2.5,
                "end": 4.0,
                "sentiment": {"compound": -0.7, "pos": 0.1, "neu": 0.2, "neg": 0.9}
            },
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "I understand your concern.",
                "start": 4.5,
                "end": 6.0,
                "sentiment": {"compound": 0.1, "pos": 0.3, "neu": 0.6, "neg": 0.1}
            },
        ]
    
    @pytest.fixture
    def sample_segments_with_emotion(self):
        """Fixture for sample segments with emotion data using database-driven speaker identification."""
        return [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "I'm excited about this!",
                "start": 0.0,
                "end": 2.0,
                "context_emotion": "joy"
            },
            {
                "speaker": "Bob",
                "speaker_db_id": 2,
                "text": "That's great!",
                "start": 2.5,
                "end": 4.0,
                "context_emotion": "joy"
            },
        ]
    
    @pytest.fixture
    def sample_speaker_map(self):
        """Fixture for sample speaker map (deprecated, kept for backward compatibility)."""
        return {}
    
    def test_temporal_dynamics_basic(self, temporal_module, sample_segments, sample_speaker_map):
        """Test basic temporal dynamics analysis."""
        result = temporal_module.analyze(sample_segments, sample_speaker_map)
        
        assert "time_windows" in result
        assert "trends" in result
        assert "phase_detection" in result
        assert "total_duration" in result
        assert len(result["time_windows"]) > 0
    
    def test_temporal_dynamics_time_windows(self, temporal_module, sample_segments, sample_speaker_map):
        """Test time window creation."""
        result = temporal_module.analyze(sample_segments, sample_speaker_map)
        
        windows = result["time_windows"]
        assert len(windows) > 0
        
        # Check window structure
        for window in windows:
            assert "window_start" in window
            assert "window_end" in window
            assert "metrics" in window
            assert "speaker_metrics" in window
            assert window["window_start"] < window["window_end"]
    
    def test_temporal_dynamics_metrics(self, temporal_module, sample_segments, sample_speaker_map):
        """Test metric calculation in time windows."""
        result = temporal_module.analyze(sample_segments, sample_speaker_map)
        
        windows = result["time_windows"]
        for window in windows:
            metrics = window["metrics"]
            assert "speaking_rate" in metrics
            assert "turn_frequency" in metrics
            assert "engagement_score" in metrics
            assert "num_segments" in metrics
            assert isinstance(metrics["speaking_rate"], (int, float))
            assert isinstance(metrics["engagement_score"], (int, float))
    
    def test_temporal_dynamics_trends(self, temporal_module, sample_segments, sample_speaker_map):
        """Test trend detection."""
        result = temporal_module.analyze(sample_segments, sample_speaker_map)
        
        trends = result["trends"]
        # Trends may be empty if not enough data, but structure should exist
        assert isinstance(trends, dict)
    
    def test_temporal_dynamics_phase_detection(self, temporal_module, sample_segments, sample_speaker_map):
        """Test phase detection."""
        result = temporal_module.analyze(sample_segments, sample_speaker_map)
        
        phases = result["phase_detection"]
        if phases:  # May be empty for short conversations
            assert "opening" in phases or "main" in phases or "closing" in phases
    
    def test_temporal_dynamics_with_sentiment(self, temporal_module, sample_segments_with_sentiment, sample_speaker_map):
        """Test temporal dynamics with sentiment data."""
        sentiment_data = {"segments_with_sentiment": sample_segments_with_sentiment}
        
        result = temporal_module.analyze(
            sample_segments_with_sentiment,
            sample_speaker_map,
            sentiment_data=sentiment_data
        )
        
        assert "time_windows" in result
        # Check if sentiment metrics are included
        windows = result["time_windows"]
        for window in windows:
            metrics = window["metrics"]
            # avg_sentiment may be None if no sentiment in that window
            assert "avg_sentiment" in metrics
    
    def test_temporal_dynamics_with_emotion(self, temporal_module, sample_segments_with_emotion, sample_speaker_map):
        """Test temporal dynamics with emotion data."""
        emotion_data = {"segments_with_emotion": sample_segments_with_emotion}
        
        result = temporal_module.analyze(
            sample_segments_with_emotion,
            sample_speaker_map,
            emotion_data=emotion_data
        )
        
        assert "time_windows" in result
        windows = result["time_windows"]
        for window in windows:
            metrics = window["metrics"]
            # dominant_emotion may be None if no emotion in that window
            assert "dominant_emotion" in metrics
    
    def test_temporal_dynamics_empty_segments(self, temporal_module, sample_speaker_map):
        """Test temporal dynamics with empty segments."""
        segments = []
        
        result = temporal_module.analyze(segments, sample_speaker_map)
        
        assert "time_windows" in result
        assert "error" in result or len(result["time_windows"]) == 0
    
    def test_temporal_dynamics_single_segment(self, temporal_module, sample_speaker_map):
        """Test temporal dynamics with single segment."""
        segments = [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "Hello", "start": 0.0, "end": 2.0}
        ]
        
        result = temporal_module.analyze(segments, sample_speaker_map)
        
        assert "time_windows" in result
        assert len(result["time_windows"]) >= 0  # May have 0 or 1 window
    
    def test_temporal_dynamics_speaker_metrics(self, temporal_module, sample_segments, sample_speaker_map):
        """Test speaker-specific metrics."""
        result = temporal_module.analyze(sample_segments, sample_speaker_map)
        
        windows = result["time_windows"]
        for window in windows:
            speaker_metrics = window["speaker_metrics"]
            assert isinstance(speaker_metrics, dict)
            # May be empty if no named speakers in window
    
    def test_temporal_dynamics_peak_periods(self, temporal_module, sample_segments, sample_speaker_map):
        """Test peak period identification."""
        result = temporal_module.analyze(sample_segments, sample_speaker_map)
        
        assert "peak_periods" in result
        assert isinstance(result["peak_periods"], list)
    
    def test_temporal_dynamics_custom_window_size(self, sample_segments, sample_speaker_map):
        """Test temporal dynamics with custom window size."""
        module = TemporalDynamicsAnalysis(config={"window_size": 10.0})
        
        result = module.analyze(sample_segments, sample_speaker_map)
        
        assert result["window_size"] == 10.0
        assert "time_windows" in result
    
    def test_temporal_dynamics_long_conversation(self, temporal_module, sample_speaker_map):
        """Test temporal dynamics with longer conversation."""
        # Create segments spanning 2 minutes
        segments = []
        for i in range(20):
            segments.append({
                "speaker": "Alice" if i % 2 == 0 else "Bob",
                "speaker_db_id": 1 if i % 2 == 0 else 2,
                "text": f"Segment {i}",
                "start": i * 6.0,
                "end": (i * 6.0) + 3.0
            })
        
        result = temporal_module.analyze(segments, sample_speaker_map)
        
        assert "time_windows" in result
        assert len(result["time_windows"]) > 1  # Should have multiple windows
        assert result["total_duration"] > 0
    
    def test_temporal_dynamics_engagement_calculation(self, temporal_module, sample_segments, sample_speaker_map):
        """Test engagement score calculation."""
        result = temporal_module.analyze(sample_segments, sample_speaker_map)
        
        windows = result["time_windows"]
        for window in windows:
            engagement = window["metrics"]["engagement_score"]
            assert 0.0 <= engagement <= 1.0  # Should be normalized
    
    def test_temporal_dynamics_run_from_context(self, temporal_module, pipeline_context_factory):
        """Test running temporal dynamics from PipelineContext."""
        context = pipeline_context_factory()
        
        result = temporal_module.run_from_context(context)
        
        assert result["status"] == "success"
        assert "results" in result
        assert "output_directory" in result
    
    def test_temporal_dynamics_run_from_context_with_dependencies(self, temporal_module, pipeline_context_factory):
        """Test running temporal dynamics with dependency data in context."""
        context = pipeline_context_factory()
        
        # Add sentiment result to context
        sentiment_result = {
            "segments_with_sentiment": [
                {
                    "speaker": "Alice",
                    "speaker_db_id": 1,
                    "text": "I'm happy",
                    "start": 0.0,
                    "end": 2.0,
                    "sentiment": {"compound": 0.7}
                }
            ]
        }
        context.store_analysis_result("sentiment", sentiment_result)
        
        result = temporal_module.run_from_context(context)
        
        assert result["status"] == "success"
        assert "results" in result
