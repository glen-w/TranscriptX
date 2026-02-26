"""
Tests for statistics service.
"""

from unittest.mock import patch, MagicMock
from datetime import datetime

from transcriptx.web.services.statistics_service import StatisticsService


class TestStatisticsService:
    """Tests for StatisticsService."""

    @patch("transcriptx.web.services.statistics_service.FileService")
    @patch("transcriptx.web.services.statistics_service.get_analysis_modules")
    @patch("transcriptx.web.services.statistics_service.get_total_module_count")
    @patch("transcriptx.web.services.statistics_service.Path")
    def test_get_session_statistics(
        self, mock_path, mock_total_count, mock_get_modules, mock_file_service
    ):
        """Test getting session statistics."""
        # Setup mocks
        mock_file_service.load_transcript_data.return_value = {
            "segments": [
                {
                    "speaker": "SPEAKER_00",
                    "text": "Hello world",
                    "start": 0.0,
                    "end": 2.0,
                },
                {"speaker": "SPEAKER_01", "text": "Hi there", "start": 3.0, "end": 5.0},
            ]
        }

        mock_get_modules.return_value = ["sentiment", "emotion"]
        mock_total_count.return_value = 18

        session_dir = MagicMock()
        session_dir.exists.return_value = True
        session_dir.stat.return_value.st_mtime = datetime.now().timestamp()

        mock_path.return_value.__truediv__ = lambda self, other: session_dir

        stats = StatisticsService.get_session_statistics("test_session")

        assert stats["segment_count"] == 2
        assert stats["speaker_count"] == 2
        assert stats["word_count"] == 4  # "Hello world" + "Hi there"
        assert stats["duration_seconds"] == 5.0
        assert stats["analysis_completion"] > 0
        assert stats["last_updated"] is not None

    @patch("transcriptx.web.services.statistics_service.FileService")
    def test_get_session_statistics_no_transcript(self, mock_file_service):
        """Test getting statistics when transcript doesn't exist."""
        mock_file_service.load_transcript_data.return_value = None

        with patch(
            "transcriptx.web.services.statistics_service.get_analysis_modules",
            return_value=[],
        ):
            with patch(
                "transcriptx.web.services.statistics_service.get_total_module_count",
                return_value=18,
            ):
                with patch(
                    "transcriptx.web.services.statistics_service.Path"
                ) as mock_path:
                    session_dir = MagicMock()
                    session_dir.exists.return_value = False
                    mock_path.return_value.__truediv__ = lambda self, other: session_dir

                    stats = StatisticsService.get_session_statistics("test_session")

                    assert stats["segment_count"] == 0
                    assert stats["speaker_count"] == 0
                    assert stats["word_count"] == 0

    @patch("transcriptx.web.services.statistics_service.FileService")
    def test_get_all_sessions_statistics(self, mock_file_service):
        """Test getting aggregate statistics."""
        mock_file_service.list_available_sessions.return_value = [
            {
                "duration_seconds": 100,
                "word_count": 500,
                "speaker_count": 2,
                "analysis_completion": 50,
                "last_updated": "2024-01-01T00:00:00",
            },
            {
                "duration_seconds": 200,
                "word_count": 1000,
                "speaker_count": 3,
                "analysis_completion": 75,
                "last_updated": "2024-01-02T00:00:00",
            },
        ]

        stats = StatisticsService.get_all_sessions_statistics()

        assert stats["total_sessions"] == 2
        assert stats["total_duration_minutes"] == 5.0  # 300 seconds / 60
        assert stats["total_word_count"] == 1500
        assert stats["total_speakers"] == 3  # max of speaker counts
        assert stats["average_completion"] == 62.5  # (50 + 75) / 2

    @patch("transcriptx.web.services.statistics_service.FileService")
    def test_get_all_sessions_statistics_empty(self, mock_file_service):
        """Test getting statistics when no sessions exist."""
        mock_file_service.list_available_sessions.return_value = []

        stats = StatisticsService.get_all_sessions_statistics()

        assert stats["total_sessions"] == 0
        assert stats["total_duration_minutes"] == 0
        assert stats["total_word_count"] == 0
        assert stats["average_completion"] == 0
