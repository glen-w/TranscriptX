"""
Tests for contagion detection and emotion merger (build_emotion_timeline, detect_contagion, merge_lexical_emotion).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


from transcriptx.core.analysis.contagion.detection import (
    build_emotion_timeline,
    detect_contagion,
)
from transcriptx.core.analysis.contagion.emotion_merger import merge_lexical_emotion


class TestDetectContagion:
    """Tests for detect_contagion (pure logic)."""

    def test_empty_timeline_returns_empty_events(self):
        events, pair_counts, summary = detect_contagion([])
        assert events == []
        assert pair_counts == []
        assert summary == {}

    def test_single_entry_timeline_returns_no_events(self):
        timeline = [("Alice", "joy")]
        events, pair_counts, summary = detect_contagion(timeline)
        assert events == []
        assert pair_counts == []
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
        by_key = {
            (r["actor"], r["target"], r["emotion"]): r["count"] for r in pair_counts
        }
        assert by_key[("Alice", "Bob", "joy")] == 1
        assert by_key[("Alice", "Bob", "sadness")] == 1
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
                    "transcriptx.utils.text_utils.is_turn_taking_speaker_label",
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

    def test_skips_unknown_placeholder_speaker(self):
        segments = [{"speaker": "Unknown", "start": 0.0, "nrc_emotion": {"joy": 0.9}}]
        with patch(
            "transcriptx.core.utils.speaker_extraction.extract_speaker_info"
        ) as mock_extract:
            with patch(
                "transcriptx.core.utils.speaker_extraction.get_speaker_display_name",
                return_value="Unknown",
            ):
                mock_extract.return_value = MagicMock(grouping_key="u0")
                speaker_emotions, timeline = build_emotion_timeline(
                    segments, "nrc_emotion"
                )
        assert len(timeline) == 0
        assert len(speaker_emotions) == 0

    def test_includes_diarization_style_speaker(self):
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
                mock_extract.return_value = MagicMock(grouping_key="s0")
                speaker_emotions, timeline = build_emotion_timeline(
                    segments, "nrc_emotion"
                )
        assert len(timeline) == 1
        assert "SPEAKER_00" in speaker_emotions


class TestMergeLexicalEmotion:
    """Tests for merge_lexical_emotion (lexical branch only)."""

    def test_empty_source_segments_merges_nothing(self):
        logger = MagicMock()
        segments = [{"speaker": "S1", "text": "Hi", "start": 0.0}]
        merged_count = merge_lexical_emotion(segments, [], logger)
        assert merged_count == 0
        assert "nrc_emotion" not in segments[0]

    def test_merges_nrc_emotion_by_segment_id(self):
        from transcriptx.core.analysis.emotion_family.fingerprints import (
            segment_text_hash,
        )

        logger = MagicMock()
        segments = [
            {"id": "s1", "speaker": "S1", "text": "Hi", "start": 0.0},
            {"id": "s2", "speaker": "S2", "text": "Bye", "start": 1.0},
        ]
        source = [
            {
                "id": "s1",
                "start": 0.0,
                "text": "Hi",
                "nrc_emotion": {"joy": 0.9, "fear": 0.1},
                "emotion_scored_text_hash": segment_text_hash("Hi"),
            },
            {
                "id": "s2",
                "start": 1.0,
                "text": "Bye",
                "nrc_emotion": {"sadness": 0.8},
                "emotion_scored_text_hash": segment_text_hash("Bye"),
            },
        ]
        merged_count = merge_lexical_emotion(segments, source, logger)
        assert merged_count == 2
        assert segments[0]["nrc_emotion"] == {"joy": 0.9, "fear": 0.1}
        assert segments[1]["nrc_emotion"] == {"sadness": 0.8}

    def test_merges_nrc_emotion_by_start_time_fallback(self):
        from transcriptx.core.analysis.emotion_family.fingerprints import (
            segment_text_hash,
        )

        logger = MagicMock()
        segments = [{"speaker": "S1", "text": "Hi", "start": 0.0}]
        source = [
            {
                "start": 0.0,
                "text": "Hi",
                "nrc_emotion": {"joy": 0.9, "fear": 0.1},
                "emotion_scored_text_hash": segment_text_hash("Hi"),
            }
        ]
        merged_count = merge_lexical_emotion(segments, source, logger)
        assert merged_count == 1
        assert segments[0]["nrc_emotion"] == {"joy": 0.9, "fear": 0.1}

    def test_rejects_merge_without_scored_text_hash(self):
        logger = MagicMock()
        segments = [{"id": "s1", "speaker": "S1", "text": "Hi", "start": 0.0}]
        source = [
            {"id": "s1", "start": 0.0, "nrc_emotion": {"joy": 0.9, "fear": 0.1}},
        ]
        merged_count = merge_lexical_emotion(segments, source, logger)
        assert merged_count == 0
        assert "nrc_emotion" not in segments[0]

    def test_never_merges_context_emotion_fields(self):
        """Contextual fields are out of scope for the lexical merger."""
        logger = MagicMock()
        segments = [{"speaker": "S1", "text": "Hi", "start": 0.0}]
        source = [
            {
                "start": 0.0,
                "context_emotion": {"joy": 0.9},
                "context_emotion_source": "contextual_emotion",
            }
        ]
        merged_count = merge_lexical_emotion(segments, source, logger)
        assert merged_count == 0
        assert "context_emotion" not in segments[0]
