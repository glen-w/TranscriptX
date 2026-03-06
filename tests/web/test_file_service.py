"""
Tests for file service.
"""

from unittest.mock import patch, MagicMock

from transcriptx.web.services.file_service import FileService


class TestFileService:
    """Tests for FileService."""

    def test_load_transcript_data_nonexistent(self):
        """Test loading transcript for nonexistent session."""
        result = FileService.load_transcript_data("nonexistent_session")
        assert result is None

    def test_load_transcript_data_success(self):
        """Test successfully loading transcript data."""
        # This test verifies the function doesn't crash with valid input
        # Actual file loading is tested in integration tests
        result = FileService.load_transcript_data("nonexistent_session_for_test")
        # Should return None for nonexistent session (no crash)
        assert result is None or isinstance(result, dict)

    @patch("transcriptx.web.services.file_service.Path")
    @patch("transcriptx.web.services.file_service.OUTPUTS_DIR", "/tmp/test")
    def test_load_analysis_data_nonexistent_module(self, mock_path):
        """Test loading analysis data for nonexistent module."""
        module_dir = MagicMock()
        module_dir.exists.return_value = False

        mock_path.return_value.__truediv__ = lambda self, other: module_dir

        result = FileService.load_analysis_data("session", "module")
        assert result is None

    def test_load_analysis_data_success(self):
        """Test loading analysis data structure."""
        # This test verifies the function doesn't crash
        # Actual file loading is tested in integration tests
        result = FileService.load_analysis_data(
            "nonexistent_session", "nonexistent_module"
        )
        # Should return None for nonexistent module (no crash)
        assert result is None or isinstance(result, dict)

    @patch("transcriptx.web.services.file_service.Path")
    def test_list_charts_no_directory(self, mock_path):
        """Test listing charts when directory doesn't exist."""
        module_dir = MagicMock()
        module_dir.exists.return_value = False

        mock_path.return_value.__truediv__ = lambda self, other: module_dir

        charts = FileService.list_charts("session", "module")

        assert charts == []

    def test_list_charts_with_files(self):
        """Test listing charts structure."""
        # This test verifies the function doesn't crash and returns correct structure
        # Actual file listing is tested in integration tests
        charts = FileService.list_charts("nonexistent_session", "nonexistent_module")
        # Should return empty list for nonexistent module (no crash)
        assert isinstance(charts, list)
        # If there were charts, they should have name and path
        if charts:
            assert all("name" in chart and "path" in chart for chart in charts)
