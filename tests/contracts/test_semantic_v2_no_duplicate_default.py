"""Default-style lists dedupe semantic_similarity_v2."""

from __future__ import annotations

from unittest.mock import patch

from transcriptx.core.analysis.selection import filter_modules_by_mode


def test_duplicate_semantic_similarity_v2_removed() -> None:
    with patch("transcriptx.core.analysis.selection.get_config") as mock_get:
        mock_config = mock_get.return_value
        mock_config.analysis.include_legacy_modules = False
        mock_config.analysis.full_analysis_settings = {"skip_advanced_semantic": False}
        out = filter_modules_by_mode(
            ["semantic_similarity_v2", "stats", "semantic_similarity_v2"],
            "full",
        )
        assert out.count("semantic_similarity_v2") == 1
