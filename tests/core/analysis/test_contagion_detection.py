"""
Tests for contagion detection and emotion merger (build_emotion_timeline, detect_contagion, merge_emotion_data).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


from transcriptx.core.analysis.contagion.detection import (
    build_emotion_timeline,
    detect_contagion,
)
from transcriptx.core.analysis.contagion.emotion_merger import merge_emotion_data


class TestDetectContagion:
    """Tests for detect_contagion (pure logic)."""

    def test_empty_timeline_returns_empty_events(self):
        events, pair_counts, summary = detect_contagion([])
        assert events == []
        assert pair_counts == {}
        assert summary == {}

    def test_single_entry_timeline_returns_no_events(self):
        timeline = [("Alice", "joy")]
        events, pair_counts, summary = detect_contagion(timeline)
        assert events == []
        assert pair_counts == {}
        assert summary == {}

    def test_contagion_same_emotion_different_speaker(self):
        timeline = [
            ("Alice", "joy"),
            ("Bob", "joy"),
            ("Alice", "sadness"),
            ("Bob", "sadness"),
        ]
        events, pair_counts, summary = detect_contagion(timeline)
        assert len(events) == 2
        assert (
            events[0]["from"] == "Alice"
            and events[0]["to"] == "Bob"
            and events[0]["emotion"] == "joy"
        )
        assert (
            events[1]["from"] == "Alice"
            and events[1]["to"] == "Bob"
            and events[1]["emotion"] == "sadness"
        )
        assert pair_counts[("Alice", "Bob", "joy")] == 1
        assert pair_counts[("Alice", "Bob", "sadness")] == 1
        assert "Alice->Bob" in summary
        assert summary["Alice->Bob"]["joy"] == 1
        assert summary["Alice->Bob"]["sadness"] == 1

    def test_no_contagion_same_speaker_consecutive(self):
        timeline = [("Alice", "joy"), ("Alice", "joy")]
        events, _, _ = detect_contagion(timeline)
        assert len(events) == 0

    def test_no_contagion_different_emotion(self):
        timeline = [("Alice", "joy"), ("Bob", "sadness")]
        events, _, _ = detect_contagion(timeline)
        assert len(events) == 0


class TestBuildEmotionTimeline:
    """Tests for build_emotion_timeline."""

    def test_nrc_emotion_type_builds_timeline(self):
        segments = [
            {
                "speaker": "Alice",
                "start": 0.0,
                "nrc_emotion": {"joy": 0.9, "fear": 0.1},
            },
            {"speaker": "Bob", "start": 1.0, "nrc_emotion": {"joy": 0.8, "fear": 0.2}},
        ]
        with patch(
            "transcriptx.core.utils.speaker_extraction.extract_speaker_info"
        ) as mock_extract:
            with patch(
                "transcriptx.core.utils.speaker_extraction.get_speaker_display_name",
                side_effect=lambda k, _, __: "Alice" if str(k) == "alice" else "Bob",
            ):
                with patch(
                    "transcriptx.utils.text_utils.is_named_speaker",
                    return_value=True,
                ):
                    mock_extract.side_effect = [
                        MagicMock(grouping_key="alice"),
                        MagicMock(grouping_key="bob"),
                    ]
                    speaker_emotions, timeline = build_emotion_timeline(
                        segments, "nrc_emotion"
                    )
        assert "Alice" in speaker_emotions and "Bob" in speaker_emotions
        assert len(timeline) == 2
        assert timeline[0][1] == "joy" and timeline[1][1] == "joy"

    def test_skips_unnamed_speaker(self):
        segments = [
            {"speaker": "SPEAKER_00", "start": 0.0, "nrc_emotion": {"joy": 0.9}}
        ]
        with patch(
            "transcriptx.core.utils.speaker_extraction.extract_speaker_info"
        ) as mock_extract:
            with patch(
                "transcriptx.core.utils.speaker_extraction.get_speaker_display_name",
                return_value="SPEAKER_00",
            ):
                with patch(
                    "transcriptx.utils.text_utils.is_named_speaker",
                    return_value=False,
                ):
                    mock_extract.return_value = MagicMock(grouping_key="s0")
                    speaker_emotions, timeline = build_emotion_timeline(
                        segments, "nrc_emotion"
                    )
        assert len(timeline) == 0
        assert len(speaker_emotions) == 0


class TestMergeEmotionData:
    """Tests for merge_emotion_data."""

    def test_empty_segments_with_emotion_returns_unchanged(self):
        logger = MagicMock()
        segments = [{"speaker": "S1", "text": "Hi", "start": 0.0}]
        merged, emotion_type, any_merged = merge_emotion_data(segments, [], logger)
        assert merged == segments
        assert emotion_type is None
        assert any_merged is False

    def test_merges_context_emotion_by_start_time(self):
        logger = MagicMock()
        segments = [
            {"speaker": "S1", "text": "Hi", "start": 0.0},
            {"speaker": "S2", "text": "Bye", "start": 1.0},
        ]
        segments_with_emotion = [
            {"start": 0.0, "context_emotion": {"joy": 0.9}},
            {"start": 1.0, "context_emotion": {"sadness": 0.8}},
        ]
        merged, emotion_type, any_merged = merge_emotion_data(
            segments, segments_with_emotion, logger
        )
        assert any_merged is True
        assert emotion_type == "context_emotion"
        assert merged[0].get("context_emotion") == {"joy": 0.9}
        assert merged[1].get("context_emotion") == {"sadness": 0.8}

    def test_merges_nrc_emotion_when_present(self):
        logger = MagicMock()
        segments = [{"speaker": "S1", "text": "Hi", "start": 0.0}]
        segments_with_emotion = [
            {"start": 0.0, "nrc_emotion": {"joy": 0.9, "fear": 0.1}},
        ]
        merged, emotion_type, any_merged = merge_emotion_data(
            segments, segments_with_emotion, logger
        )
        assert any_merged is True
        assert merged[0].get("nrc_emotion") == {"joy": 0.9, "fear": 0.1}
