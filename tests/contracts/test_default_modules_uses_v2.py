"""Default semantic path uses v2; analysis_mode drives v2.mode via settings."""

from __future__ import annotations

from unittest.mock import patch

from transcriptx.core.analysis.selection import apply_analysis_mode_settings


def test_apply_full_mode_sets_v2_mode_advanced() -> None:
    with patch("transcriptx.core.analysis.selection.get_config") as mock_get:
        mock_config = mock_get.return_value
        mock_config.analysis.full_analysis_settings = {
            "semantic_method": "advanced",
            "max_segments_for_semantic": 1000,
            "max_semantic_comparisons": 30000,
            "ner_use_light_model": False,
            "ner_max_segments": 5000,
            "skip_advanced_semantic": False,
            "skip_geocoding": False,
        }
        mock_config.analysis.semantic_similarity_v2.mode = "basic"
        apply_analysis_mode_settings("full", "balanced")
        assert mock_config.analysis.semantic_similarity_v2.mode == "advanced"


def test_apply_quick_mode_sets_v2_mode_basic() -> None:
    with patch("transcriptx.core.analysis.selection.get_config") as mock_get:
        mock_config = mock_get.return_value
        mock_config.analysis.quick_analysis_settings = {
            "semantic_method": "simple",
            "max_segments_for_semantic": 800,
            "max_semantic_comparisons": 15000,
            "ner_use_light_model": False,
            "ner_max_segments": 2000,
            "skip_advanced_semantic": True,
            "skip_geocoding": False,
            "semantic_profile": "balanced",
        }
        mock_config.analysis.semantic_similarity_v2.mode = "advanced"
        apply_analysis_mode_settings("quick")
        assert mock_config.analysis.semantic_similarity_v2.mode == "basic"
