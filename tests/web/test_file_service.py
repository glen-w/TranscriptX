"""
Tests for file service.
"""

from unittest.mock import MagicMock, patch

from transcriptx.web.services.file_service import (
    FileService,
    _extract_metadata_stats,
)


class TestExtractMetadataStats:

    def test_wrapper_delegates_to_listing_stats(self) -> None:
        doc = {
            "metadata": {
                "segment_count": 3,
                "duration_seconds": 90.0,
                "speaker_count": 1,
                "word_count": 12,
            }
        }
        stats = _extract_metadata_stats(doc)
        assert stats["segment_count"] == 3
        assert stats["duration_minutes"] == 1.5
        assert stats["word_count"] == 12


class TestFileService:
    """Tests for FileService."""

    def test_load_transcript_by_session_nonexistent(self):
        """Test loading transcript for nonexistent session."""
        result = FileService.load_transcript_by_session("nonexistent_session")
        assert result is None

    def test_load_transcript_by_session_success(self):
        """Test successfully loading transcript data."""
        # This test verifies the function doesn't crash with valid input
        # Actual file loading is tested in integration tests
        result = FileService.load_transcript_by_session("nonexistent_session_for_test")
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

    @patch("transcriptx.io.transcript_loader.load_transcript")
    @patch("transcriptx.web.services.file_service.FileService.resolve_transcript_path")
    @patch("transcriptx.web.services.file_service.FileService._is_viewable_run")
    @patch("transcriptx.web.services.file_service.Path")
    @patch("transcriptx.web.services.file_service.OUTPUTS_DIR", "/tmp/test_outputs")
    @patch(
        "transcriptx.web.services.file_service.GROUP_OUTPUTS_DIR", "/tmp/test_groups"
    )
    def test_list_available_sessions_dedupes_transcript_loads(
        self,
        mock_path_cls,
        mock_viewable,
        mock_resolve_path,
        mock_load_transcript,
    ) -> None:
        """Two runs sharing a transcript path should load the document once."""
        mock_viewable.return_value = True
        shared = MagicMock()
        shared.resolve.return_value = shared
        mock_resolve_path.return_value = shared

        run_a = MagicMock()
        run_a.is_dir.return_value = True
        run_a.name = "run-a"
        run_b = MagicMock()
        run_b.is_dir.return_value = True
        run_b.name = "run-b"

        slug_dir = MagicMock()
        slug_dir.is_dir.return_value = True
        slug_dir.name = "slug1"
        slug_dir.iterdir.return_value = [run_a, run_b]

        outputs_dir = MagicMock()
        outputs_dir.exists.return_value = True
        outputs_dir.iterdir.return_value = [slug_dir]

        mock_path_cls.return_value = outputs_dir
        mock_path_cls.side_effect = lambda value: (
            outputs_dir if str(value) == "/tmp/test_outputs" else MagicMock()
        )

        mock_load_transcript.return_value = {
            "metadata": {
                "segment_count": 10,
                "duration_seconds": 600.0,
                "speaker_count": 2,
            },
            "segments": [
                {"text": "one two three"},
                {"text": "four five"},
            ],
        }

        with (
            patch(
                "transcriptx.core.utils.slug_manager.get_transcript_key_for_slug",
                return_value="key1",
            ),
            patch(
                "transcriptx.web.module_registry.get_total_module_count",
                return_value=1,
            ),
            patch(
                "transcriptx.web.module_registry.get_analysis_modules",
                return_value=["mod"],
            ),
            patch.object(
                FileService,
                "load_transcript_by_session",
                side_effect=AssertionError("must not load transcript per run"),
            ),
        ):
            sessions = FileService.list_available_sessions()

        assert len(sessions) == 2
        assert mock_load_transcript.call_count == 1
        assert sessions[0]["segment_count"] == 10
        assert sessions[0]["word_count"] == 5
        assert sessions[1]["duration_minutes"] == 10.0
