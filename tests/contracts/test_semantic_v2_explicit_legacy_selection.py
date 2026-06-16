"""Explicit legacy semantic IDs are preserved when include_legacy_modules is False."""

from __future__ import annotations

from unittest.mock import patch

from transcriptx.core.analysis.selection import filter_modules_by_mode


def test_explicit_legacy_semantic_survives_filter_full_mode() -> None:
    with patch("transcriptx.core.analysis.selection.get_config") as mock_get:
        mock_config = mock_get.return_value
        mock_config.analysis.include_legacy_modules = False
        mock_config.analysis.full_analysis_settings = {"skip_advanced_semantic": False}
        out = filter_modules_by_mode(
            ["stats", "semantic_similarity"],
            "full",
        )
        assert "semantic_similarity" in out


def test_explicit_advanced_replaced_with_basic_legacy_in_quick() -> None:
    with patch("transcriptx.core.analysis.selection.get_config") as mock_get:
        mock_config = mock_get.return_value
        mock_config.analysis.include_legacy_modules = False
        mock_config.analysis.quick_analysis_settings = {"skip_advanced_semantic": True}
        out = filter_modules_by_mode(
            ["stats", "semantic_similarity_advanced"],
            "quick",
        )
        assert "semantic_similarity_advanced" not in out
        assert "semantic_similarity" in out
