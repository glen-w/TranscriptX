"""
Tests for utils.py backward compatibility.

Ensures that the refactored utils.py still maintains the same
interface for existing code.
"""

from unittest.mock import patch

from transcriptx.web.utils import (
    get_session_statistics,
    load_transcript_data,
    get_analysis_modules,
    load_analysis_data,
    list_charts,
    get_all_sessions_statistics,
    extract_analysis_summary,
)


class TestUtilsBackwardCompatibility:
    """Tests to ensure utils.py maintains backward compatibility."""

    def test_get_session_statistics_delegates(self):
        """Test that get_session_statistics delegates to service."""
        with patch("transcriptx.web.utils.StatisticsService") as mock_service:
            mock_service.get_session_statistics.return_value = {"test": "data"}

            result = get_session_statistics("test_session")

            mock_service.get_session_statistics.assert_called_once_with("test_session")
            assert result == {"test": "data"}

    def test_load_transcript_data_delegates(self):
        """Test that load_transcript_data delegates to service."""
        with patch("transcriptx.web.utils.FileService") as mock_service:
            mock_service.load_transcript_data.return_value = {"segments": []}

            result = load_transcript_data("test_session")

            mock_service.load_transcript_data.assert_called_once_with("test_session")
            assert result == {"segments": []}

    def test_get_analysis_modules_delegates(self):
        """Test that get_analysis_modules delegates to module registry."""
        with patch(
            "transcriptx.web.module_registry.get_analysis_modules"
        ) as mock_registry:
            mock_registry.return_value = ["sentiment", "emotion"]

            result = get_analysis_modules("test_session")

            mock_registry.assert_called_once_with("test_session")
            assert result == ["sentiment", "emotion"]

    def test_load_analysis_data_delegates(self):
        """Test that load_analysis_data delegates to service."""
        with patch("transcriptx.web.utils.FileService") as mock_service:
            mock_service.load_analysis_data.return_value = {"test": "data"}

            result = load_analysis_data("test_session", "sentiment")

            mock_service.load_analysis_data.assert_called_once_with(
                "test_session", "sentiment"
            )
            assert result == {"test": "data"}

    def test_list_charts_delegates(self):
        """Test that list_charts delegates to service."""
        with patch("transcriptx.web.utils.FileService") as mock_service:
            mock_service.list_charts.return_value = [{"name": "chart.png"}]

            result = list_charts("test_session", "sentiment")

            mock_service.list_charts.assert_called_once_with(
                "test_session", "sentiment"
            )
            assert result == [{"name": "chart.png"}]

    def test_get_all_sessions_statistics_delegates(self):
        """Test that get_all_sessions_statistics delegates to service."""
        with patch("transcriptx.web.utils.StatisticsService") as mock_service:
            mock_service.get_all_sessions_statistics.return_value = {
                "total_sessions": 5
            }

            result = get_all_sessions_statistics()

            mock_service.get_all_sessions_statistics.assert_called_once()
            assert result == {"total_sessions": 5}

    def test_extract_analysis_summary_delegates(self):
        """Test that extract_analysis_summary delegates to service."""
        with patch("transcriptx.web.utils.SummaryService") as mock_service:
            mock_service.extract_analysis_summary.return_value = {
                "has_data": True,
                "key_metrics": {},
                "highlights": [],
            }

            result = extract_analysis_summary("sentiment", {"test": "data"})

            mock_service.extract_analysis_summary.assert_called_once_with(
                "sentiment", {"test": "data"}
            )
            assert result["has_data"] is True
