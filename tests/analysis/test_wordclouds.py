"""
Tests for wordclouds analysis module.

This module tests word cloud generation.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch
import pytest

from transcriptx.core.analysis.wordclouds import WordcloudsAnalysis  # type: ignore[import-untyped]
from transcriptx.core.analysis.wordclouds.analysis import (
    _build_wordcloud_explorer_html,
    _should_generate_views,
    group_texts_by_speaker,
)
from transcriptx.core.utils.config import TranscriptXConfig, get_config, set_config


class TestWordcloudExplorerHtml:
    """Contract tests for dynamic wordcloud explorer HTML."""

    @pytest.fixture
    def restore_config(self):
        original = get_config()
        yield
        set_config(original)

    def test_should_generate_views_on_auto_off(self, restore_config) -> None:
        """Only dynamic_views=off skips; on and auto both enable views."""
        for mode, expected in (("off", False), ("on", True), ("auto", True)):
            cfg = TranscriptXConfig()
            cfg.output.dynamic_views = mode  # type: ignore[assignment]
            set_config(cfg)
            assert _should_generate_views() is expected

    def test_build_wordcloud_explorer_html_contract(self) -> None:
        """Explorer uses wordcloud2 CDN, canvas, payload embed, table shell, empty state."""
        payload = {
            "source": "wordclouds",
            "variant": "basic",
            "terms": [
                {"term": "alpha", "value": 9.0, "rank": 1},
                {"term": "beta", "value": 4.0, "rank": 2},
            ],
        }
        html = _build_wordcloud_explorer_html("Test Cloud", payload)
        assert "cdn.jsdelivr.net/npm/wordcloud@1.2.2/src/wordcloud2.js" in html
        assert 'id="wordcloudCanvas"' in html
        assert "window.WORDCLOUD_TERMS" in html
        assert '"alpha"' in html and '"terms"' in html
        assert "plot.ly" not in html
        assert "Plotly.newPlot" not in html
        assert "<table>" in html
        assert "<thead>" in html and "<tbody>" in html
        assert "<th>Rank</th>" in html
        assert "<th>Term</th>" in html
        assert "<th>Value</th>" in html
        assert 'id="wordcloudEmptyState"' in html
        assert 'data-wordcloud-empty="1"' in html


class TestWordcloudsAnalysis:
    """Tests for WordcloudsAnalysis."""

    @pytest.fixture
    def wordclouds_module(self) -> WordcloudsAnalysis:
        """Fixture for WordcloudsAnalysis instance."""
        return WordcloudsAnalysis()

    @pytest.fixture
    def sample_segments(self) -> list[dict[str, Any]]:
        """Fixture for sample transcript segments with segment-based speaker identification."""
        return [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "I love machine learning and data science.",
                "start": 0.0,
                "end": 2.0,
            },
            {
                "speaker": "Bob",
                "speaker_db_id": 2,
                "text": "Python is great for programming and analysis.",
                "start": 2.0,
                "end": 4.0,
            },
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "Deep learning models are fascinating.",
                "start": 4.0,
                "end": 6.0,
            },
        ]

    @pytest.fixture
    def sample_speaker_map(self) -> dict[str, str]:
        """Fixture for sample speaker map (deprecated, kept for backward compatibility)."""
        return {}

    @patch("transcriptx.core.analysis.wordclouds.analysis.group_texts_by_speaker")
    def test_wordclouds_basic(
        self,
        mock_group_texts: Any,
        wordclouds_module: WordcloudsAnalysis,
        sample_segments: list[dict[str, Any]],
        sample_speaker_map: dict[str, str],
    ) -> None:
        """Test basic wordcloud analysis."""
        # Mock group_texts
        mock_group_texts.return_value = {
            "Alice": [
                "I love machine learning and data science.",
                "Deep learning models are fascinating.",
            ],
            "Bob": ["Python is great for programming and analysis."],
        }

        # Provide tic_list explicitly to keep this test pure/offline.
        result = wordclouds_module.analyze(sample_segments, tic_list=[])

        assert "grouped_texts" in result

    @patch("transcriptx.core.analysis.wordclouds.analysis.group_texts_by_speaker")
    def test_wordclouds_with_tic_list(
        self,
        mock_group_texts: Any,
        wordclouds_module: WordcloudsAnalysis,
        sample_segments: list[dict[str, Any]],
        sample_speaker_map: dict[str, str],
    ) -> None:
        """Test wordcloud analysis with provided tic list."""
        mock_group_texts.return_value = {
            "Alice": ["I love machine learning."],
            "Bob": ["Python is great."],
        }

        tic_list = ["um", "uh", "like"]

        result = wordclouds_module.analyze(sample_segments, tic_list=tic_list)

        assert "tic_list" in result
        assert result["tic_list"] == tic_list

    @patch("transcriptx.core.analysis.wordclouds.analysis.group_texts_by_speaker")
    def test_wordclouds_empty_segments(
        self,
        mock_group_texts: Any,
        wordclouds_module: WordcloudsAnalysis,
        sample_speaker_map: dict[str, str],
    ) -> None:
        """Test wordcloud analysis with empty segments."""
        segments: list[dict[str, Any]] = []
        mock_group_texts.return_value = {}

        result = wordclouds_module.analyze(segments, tic_list=[])

        assert "grouped_texts" in result

    def test_group_texts_by_speaker_falls_back_for_placeholder_names(self) -> None:
        """Fallback keeps SPEAKER_XX groups when no named speakers exist."""
        segments = [
            {"speaker": "SPEAKER_00", "text": "hello"},
            {"speaker": "SPEAKER_01", "text": "world"},
        ]
        grouped = group_texts_by_speaker(segments)
        assert set(grouped.keys()) == {"SPEAKER_00", "SPEAKER_01"}

    def test_wordclouds_uses_eligibility_filtered_segments_when_available(
        self, wordclouds_module: WordcloudsAnalysis
    ) -> None:
        wordclouds_module._eligibility_result = {
            "filtered_segments": [
                {"speaker": "Alice", "content_text": "battery storage plan"},
                {"speaker": "Bob", "content_text": "grid reliability"},
            ],
            "tic_mask": ["like", "you know"],
        }
        result = wordclouds_module.analyze([], tic_list=None)
        assert result["eligibility_fallback"] is False
        assert result["grouped_texts"]["Alice"] == ["battery storage plan"]
        assert result["grouped_texts"]["Bob"] == ["grid reliability"]
        assert sorted(result["tic_list"]) == ["like", "you know"]

    @patch("transcriptx.core.analysis.wordclouds.analysis.group_texts_by_speaker")
    def test_wordclouds_fallback_without_eligibility(
        self,
        mock_group_texts: Any,
        wordclouds_module: WordcloudsAnalysis,
        sample_segments: list[dict[str, Any]],
    ) -> None:
        mock_group_texts.return_value = {"Alice": ["raw text"]}
        wordclouds_module._eligibility_result = {}
        result = wordclouds_module.analyze(sample_segments, tic_list=[])
        assert result["eligibility_fallback"] is True
        assert result["grouped_texts"] == {"Alice": ["raw text"]}
