"""
Tests for insights_normalization (SegmentLite contract, sentiment/emotion maps).
"""

from __future__ import annotations


# Import via highlights to avoid circular import (highlights -> insights_normalization -> highlights.core)
from transcriptx.core.analysis.highlights import normalize_segments


class TestNormalizeSegments:
    """Tests for normalize_segments."""

    def test_empty_segments_returns_empty_list(self):
        assert normalize_segments([]) == []

    def test_segments_without_context_use_segment_fields(self):
        segments = [
            {
                "speaker": "S1",
                "text": "Hello",
                "start": 0.0,
                "end": 1.0,
                "segment_index": 0,
            }
        ]
        result = normalize_segments(segments, transcript_key="tk")
        assert len(result) == 1
        assert result[0].speaker_display == "S1"
        assert result[0].text == "Hello"
        assert result[0].segment_index == 0
        assert result[0].segment_key == "idx:tk:0"

    def test_segment_key_uses_segment_db_id_when_present(self):
        segments = [
            {
                "speaker": "S1",
                "text": "Hi",
                "start": 0.0,
                "end": 1.0,
                "segment_db_id": 42,
                "segment_index": 0,
            }
        ]
        result = normalize_segments(segments)
        assert len(result) == 1
        assert result[0].segment_key == "db:42"

    def test_segment_key_uses_segment_uuid_when_present(self):
        segments = [
            {
                "speaker": "S1",
                "text": "Hi",
                "start": 0.0,
                "end": 1.0,
                "segment_uuid": "abc-123",
                "segment_index": 0,
            }
        ]
        result = normalize_segments(segments)
        assert len(result) == 1
        assert result[0].segment_key == "uuid:abc-123"

    def test_sentiment_from_context_injected_into_segment(self):
        class MockContext:
            def get_analysis_result(self, name):
                if name == "sentiment":
                    return {
                        "segments_with_sentiment": [
                            {"segment_index": 0, "sentiment": {"compound": 0.5}}
                        ]
                    }
                return None

        segments = [
            {
                "speaker": "S1",
                "text": "Hi",
                "start": 0.0,
                "end": 1.0,
                "segment_index": 0,
            }
        ]
        result = normalize_segments(segments, context=MockContext())
        assert len(result) == 1
        assert result[0].sentiment_compound == 0.5

    def test_emotion_from_context_injected_into_segment(self):
        class MockContext:
            def get_analysis_result(self, name):
                if name == "emotion":
                    return {
                        "segments_with_emotion": [
                            {
                                "segment_index": 0,
                                "nrc_emotion": {"joy": 0.8},
                                "context_emotion": {"joy": 0.9},
                            }
                        ]
                    }
                return None

        segments = [
            {
                "speaker": "S1",
                "text": "Hi",
                "start": 0.0,
                "end": 1.0,
                "segment_index": 0,
            }
        ]
        result = normalize_segments(segments, context=MockContext())
        assert len(result) == 1
        assert result[0].emotion_dist == {"joy": 0.8}
        assert result[0].context_emotion == {"joy": 0.9}

    def test_sentiment_from_segment_when_not_in_context(self):
        segments = [
            {
                "speaker": "S1",
                "text": "Hi",
                "start": 0.0,
                "end": 1.0,
                "segment_index": 0,
                "sentiment": {"compound": -0.2},
            }
        ]
        result = normalize_segments(segments)
        assert len(result) == 1
        assert result[0].sentiment_compound == -0.2

    def test_speaker_display_fallback_to_speaker(self):
        segments = [
            {
                "speaker": "Alice",
                "text": "Hi",
                "start": 0.0,
                "end": 1.0,
                "segment_index": 0,
            }
        ]
        result = normalize_segments(segments)
        assert result[0].speaker_display == "Alice"

    def test_segment_index_defaults_to_enumerate_index(self):
        segments = [
            {"speaker": "S1", "text": "A", "start": 0.0, "end": 1.0},
            {"speaker": "S2", "text": "B", "start": 1.0, "end": 2.0},
        ]
        result = normalize_segments(segments)
        assert result[0].segment_index == 0
        assert result[1].segment_index == 1
