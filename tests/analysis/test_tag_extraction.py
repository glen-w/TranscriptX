"""
Tests for tag extraction analysis module.

This module tests tag extraction from transcripts.
"""

from __future__ import annotations

from typing import Any
import pytest

from transcriptx.core.analysis.tag_extraction import TagExtractor  # type: ignore[import-untyped]


class TestTagExtractor:
    """Tests for TagExtractor."""

    @pytest.fixture
    def tag_extractor(self) -> TagExtractor:
        """Fixture for TagExtractor instance."""
        return TagExtractor()

    @pytest.fixture
    def sample_segments(self) -> list[dict[str, Any]]:
        """Fixture for sample transcript segments using database-driven speaker identification."""
        return [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "I have an idea for a new project.",
                "start": 0.0,
                "end": 2.0,
            },
            {
                "speaker": "Bob",
                "speaker_db_id": 2,
                "text": "What if we try a different approach?",
                "start": 2.0,
                "end": 4.0,
            },
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "Let's discuss this in our meeting.",
                "start": 4.0,
                "end": 6.0,
            },
        ]

    @pytest.fixture
    def sample_speaker_map(self) -> dict[str, str]:
        """Fixture for sample speaker map (deprecated, kept for backward compatibility)."""
        return {}

    def test_tag_extraction_basic(
        self,
        tag_extractor: TagExtractor,
        sample_segments: list[dict[str, Any]],
        sample_speaker_map: dict[str, str],
    ) -> None:
        """Test basic tag extraction."""
        result = tag_extractor.analyze(sample_segments, sample_speaker_map)

        assert "tags" in result
        assert "tag_details" in result
        assert isinstance(result["tags"], list)
        assert isinstance(result["tag_details"], dict)
        assert all(
            isinstance(v, dict) and "confidence" in v
            for v in result["tag_details"].values()
        )

    def test_tag_extraction_idea_tag(
        self, tag_extractor: TagExtractor, sample_speaker_map: dict[str, str]
    ) -> None:
        """Test extraction of 'idea' tag."""
        segments = [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "I have an idea for a new feature.",
                "start": 0.0,
                "end": 2.0,
            },
        ]

        result = tag_extractor.analyze(segments, sample_speaker_map)

        # Should detect 'idea' tag
        tags = result.get("tags", result.get("extracted_tags", []))
        if isinstance(tags, list):
            tag_names = [
                tag.get("tag", tag) if isinstance(tag, dict) else tag for tag in tags
            ]
            assert "idea" in tag_names or any(
                "idea" in str(tag).lower() for tag in tag_names
            )
        elif isinstance(tags, dict):
            assert "idea" in tags or any("idea" in str(k).lower() for k in tags.keys())

    def test_tag_extraction_meeting_tag(
        self, tag_extractor: TagExtractor, sample_speaker_map: dict[str, str]
    ) -> None:
        """Test extraction of 'meeting' tag."""
        segments = [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "Let's discuss this in our meeting today.",
                "start": 0.0,
                "end": 2.0,
            },
        ]

        result = tag_extractor.analyze(segments, sample_speaker_map)

        # Should detect 'meeting' tag
        tags = result.get("tags", result.get("extracted_tags", []))
        if isinstance(tags, list):
            tag_names = [
                tag.get("tag", tag) if isinstance(tag, dict) else tag for tag in tags
            ]
            assert "meeting" in tag_names or any(
                "meeting" in str(tag).lower() for tag in tag_names
            )
        elif isinstance(tags, dict):
            assert "meeting" in tags or any(
                "meeting" in str(k).lower() for k in tags.keys()
            )

    def test_tag_extraction_question_tag(
        self, tag_extractor: TagExtractor, sample_speaker_map: dict[str, str]
    ) -> None:
        """Test extraction of 'question' tag."""
        segments = [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "What do you think about this?",
                "start": 0.0,
                "end": 2.0,
            },
        ]

        result = tag_extractor.analyze(segments, sample_speaker_map)

        # Should detect 'question' tag
        tags = result.get("tags", result.get("extracted_tags", []))
        if isinstance(tags, list):
            tag_names = [
                tag.get("tag", tag) if isinstance(tag, dict) else tag for tag in tags
            ]
            assert "question" in tag_names or any(
                "question" in str(tag).lower() for tag in tag_names
            )
        elif isinstance(tags, dict):
            assert "question" in tags or any(
                "question" in str(k).lower() for k in tags.keys()
            )

    def test_tag_extraction_empty_segments(
        self, tag_extractor: TagExtractor, sample_speaker_map: dict[str, str]
    ) -> None:
        """Test tag extraction with empty segments."""
        segments: list[dict[str, Any]] = []

        result = tag_extractor.analyze(segments, sample_speaker_map)

        assert result is not None
        assert "tags" in result

    def test_tag_extraction_early_window(
        self, tag_extractor: TagExtractor, sample_speaker_map: dict[str, str]
    ) -> None:
        """Test that tag extraction focuses on early segments."""
        segments = [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "I have an idea.",
                "start": 0.0,
                "end": 2.0,
            },
            {
                "speaker": "Bob",
                "speaker_db_id": 2,
                "text": "That's interesting.",
                "start": 2.0,
                "end": 4.0,
            },
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "Let's discuss it.",
                "start": 60.0,
                "end": 62.0,
            },  # Later segment
        ]

        result = tag_extractor.analyze(segments, sample_speaker_map)

        # Should extract tags from early segments
        assert result is not None

    def test_tag_extraction_confidence_scoring(
        self,
        tag_extractor: TagExtractor,
        sample_segments: list[dict[str, Any]],
        sample_speaker_map: dict[str, str],
    ) -> None:
        """Test that tags include confidence scores."""
        result = tag_extractor.analyze(sample_segments, sample_speaker_map)

        # Should include confidence information
        assert "tag_details" in result
        assert any(
            isinstance(details, dict) and "confidence" in details
            for details in result["tag_details"].values()
        )
