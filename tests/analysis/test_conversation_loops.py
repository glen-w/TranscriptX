"""
Tests for conversation loops analysis module.

This module tests loop detection and pattern recognition.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch
import pytest

from transcriptx.core.analysis.conversation_loops import ConversationLoopDetector, ConversationLoop


class TestConversationLoopDetector:
    """Tests for ConversationLoopDetector."""
    
    @pytest.fixture
    def detector(self) -> ConversationLoopDetector:
        """Fixture for ConversationLoopDetector instance."""
        return ConversationLoopDetector()
    
    @pytest.fixture
    def sample_segments(self) -> list[dict[str, Any]]:
        """Fixture for sample transcript segments with conversation loops using database-driven speaker identification."""
        return [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "What do you think?", "start": 0.0, "end": 2.0},
            {"speaker": "Bob", "speaker_db_id": 2, "text": "I think it's good.", "start": 2.0, "end": 4.0},
            {"speaker": "Alice", "speaker_db_id": 1, "text": "Thanks for your input.", "start": 4.0, "end": 6.0},
            {"speaker": "Alice", "speaker_db_id": 1, "text": "Can you help me?", "start": 6.0, "end": 8.0},
            {"speaker": "Bob", "speaker_db_id": 2, "text": "Sure, I can help.", "start": 8.0, "end": 10.0},
            {"speaker": "Alice", "speaker_db_id": 1, "text": "Great!", "start": 10.0, "end": 11.0},
        ]
    
    @pytest.fixture
    def sample_speaker_map(self) -> dict[str, str]:
        """Fixture for sample speaker map (deprecated, kept for backward compatibility)."""
        return {}
    
    @patch("transcriptx.core.analysis.conversation_loops.analysis.classify_utterance")
    def test_detect_loops_basic(
        self,
        mock_classify: Any,
        detector: ConversationLoopDetector,
        sample_segments: list[dict[str, Any]],
        sample_speaker_map: dict[str, str],
    ) -> None:
        """Test basic loop detection."""
        # Mock classify_utterance to return appropriate act types
        def mock_classify_func(text):
            if "?" in text:
                return "question"
            elif "Thanks" in text or "Great" in text:
                return "statement"
            else:
                return "statement"
        
        mock_classify.side_effect = mock_classify_func
        
        loops = detector.detect_loops(sample_segments, sample_speaker_map)
        
        assert isinstance(loops, list)
        # Should detect at least one loop (SPEAKER_00 question -> SPEAKER_01 response -> SPEAKER_00 response)
        assert len(loops) > 0
    
    @pytest.mark.slow
    @patch("transcriptx.core.analysis.conversation_loops.analysis.classify_utterance")
    def test_detect_loops_no_loops(
        self,
        mock_classify: Any,
        detector: ConversationLoopDetector,
        sample_speaker_map: dict[str, str],
    ) -> None:
        """Test loop detection with no loops."""
        segments = [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "Hello.", "start": 0.0, "end": 1.0},
            {"speaker": "Bob", "speaker_db_id": 2, "text": "Hi there.", "start": 1.0, "end": 2.0},
        ]
        
        mock_classify.return_value = "statement"
        
        loops = detector.detect_loops(segments, sample_speaker_map)
        
        assert isinstance(loops, list)
        # No loops should be detected
        assert len(loops) == 0
    
    @patch("transcriptx.core.analysis.conversation_loops.analysis.classify_utterance")
    def test_detect_loops_empty_segments(
        self,
        mock_classify: Any,
        detector: ConversationLoopDetector,
        sample_speaker_map: dict[str, str],
    ) -> None:
        """Test loop detection with empty segments."""
        segments = []
        
        loops = detector.detect_loops(segments, sample_speaker_map)
        
        assert isinstance(loops, list)
        assert len(loops) == 0
    
    @patch("transcriptx.core.analysis.conversation_loops.analysis.classify_utterance")
    @patch("transcriptx.core.analysis.conversation_loops.analysis.score_sentiment")
    def test_loop_structure(
        self,
        mock_sentiment: Any,
        mock_classify: Any,
        detector: ConversationLoopDetector,
        sample_segments: list[dict[str, Any]],
        sample_speaker_map: dict[str, str],
    ) -> None:
        """Test that detected loops have correct structure."""
        mock_classify.return_value = "question"
        mock_sentiment.return_value = {"compound": 0.5, "pos": 0.6, "neu": 0.3, "neg": 0.1}
        
        loops = detector.detect_loops(sample_segments, sample_speaker_map)
        
        if loops:
            loop = loops[0]
            assert hasattr(loop, 'speaker_a') or 'speaker_a' in loop.__dict__
            assert hasattr(loop, 'speaker_b') or 'speaker_b' in loop.__dict__
            assert hasattr(loop, 'turn_1_text') or 'turn_1_text' in loop.__dict__
            assert hasattr(loop, 'turn_2_text') or 'turn_2_text' in loop.__dict__
            assert hasattr(loop, 'turn_3_text') or 'turn_3_text' in loop.__dict__


class TestConversationLoopsAnalysis:
    """Tests for ConversationLoopsAnalysis module."""
    
    @pytest.fixture
    def sample_segments(self) -> list[dict[str, Any]]:
        """Fixture for sample transcript segments using database-driven speaker identification."""
        return [
            {"speaker": "Alice", "speaker_db_id": 1, "text": "What do you think?", "start": 0.0, "end": 2.0},
            {"speaker": "Bob", "speaker_db_id": 2, "text": "I think it's good.", "start": 2.0, "end": 4.0},
            {"speaker": "Alice", "speaker_db_id": 1, "text": "Thanks!", "start": 4.0, "end": 5.0},
        ]
    
    @pytest.fixture
    def sample_speaker_map(self) -> dict[str, str]:
        """Fixture for sample speaker map (deprecated, kept for backward compatibility)."""
        return {}
    
    @patch('transcriptx.core.analysis.conversation_loops.ConversationLoopDetector')
    def test_analyze_loops(
        self,
        mock_detector_class: Any,
        sample_segments: list[dict[str, Any]],
        sample_speaker_map: dict[str, str],
    ) -> None:
        """Test analyze method of ConversationLoopsAnalysis."""
        from transcriptx.core.analysis.conversation_loops import ConversationLoopsAnalysis
        
        # Mock detector
        mock_detector = MagicMock()
        mock_loop = MagicMock()
        mock_loop.speaker_a = "Alice"
        mock_loop.speaker_b = "Bob"
        mock_detector.detect_loops.return_value = [mock_loop]
        mock_detector_class.return_value = mock_detector
        
        module = ConversationLoopsAnalysis()
        result = module.analyze(sample_segments, sample_speaker_map)
        
        assert "loops" in result or "conversation_loops" in result
        assert "summary" in result or "statistics" in result
