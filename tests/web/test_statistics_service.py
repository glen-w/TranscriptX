"""
Tests for statistics service.
"""

from unittest.mock import patch, MagicMock
from datetime import datetime
from pathlib import Path

from transcriptx.web.services.statistics_service import (
    StatisticsService,
    _manifest_artifact_bytes,
    _total_artifact_bytes,
)


class TestStatisticsService:
    """Tests for StatisticsService."""

    @patch("transcriptx.web.services.statistics_service.cached_list_available_sessions")
    @patch("transcriptx.web.services.statistics_service.FileService")
    @patch("transcriptx.web.services.statistics_service.get_analysis_modules")
    @patch("transcriptx.web.services.statistics_service.get_total_module_count")
    @patch("transcriptx.web.services.statistics_service.Path")
    def test_get_session_statistics(
        self,
        mock_path,
        mock_total_count,
        mock_get_modules,
        mock_file_service,
        mock_list_sessions,
    ):
        """Test getting session statistics."""
        mock_list_sessions.return_value = []
        # Setup mocks
        mock_file_service.load_transcript_by_session.return_value = {
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

    @patch("transcriptx.web.services.statistics_service.cached_list_available_sessions")
    @patch("transcriptx.web.services.statistics_service.get_analysis_modules")
    @patch("transcriptx.web.services.statistics_service.get_total_module_count")
    @patch("transcriptx.web.services.statistics_service.Path")
    def test_get_session_statistics_prefers_listing_entry(
        self, mock_path, mock_total_count, mock_get_modules, mock_list_sessions
    ):
        mock_list_sessions.return_value = [
            {
                "name": "slug/run-a",
                "segment_count": 9,
                "duration_seconds": 120.0,
                "speaker_count": 4,
                "word_count": 800,
            }
        ]
        mock_get_modules.return_value = []
        mock_total_count.return_value = 18
        session_dir = MagicMock()
        session_dir.exists.return_value = False
        mock_path.return_value.__truediv__ = lambda self, other: session_dir

        stats = StatisticsService.get_session_statistics("slug/run-a")

        assert stats["segment_count"] == 9
        assert stats["duration_seconds"] == 120.0
        assert stats["speaker_count"] == 4
        assert stats["word_count"] == 800

    @patch("transcriptx.web.services.statistics_service.cached_list_available_sessions")
    @patch("transcriptx.web.services.statistics_service.FileService")
    def test_get_session_statistics_no_transcript(
        self, mock_file_service, mock_list_sessions
    ):
        """Test getting statistics when transcript doesn't exist."""
        mock_list_sessions.return_value = []
        mock_file_service.load_transcript_by_session.return_value = None

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

    @patch("transcriptx.web.services.statistics_service.cached_list_available_sessions")
    @patch("transcriptx.web.services.statistics_service._total_artifact_bytes")
    def test_get_all_sessions_statistics(self, mock_artifact_bytes, mock_list_sessions):
        """Test getting aggregate statistics."""
        mock_artifact_bytes.return_value = 4096
        mock_list_sessions.return_value = [
            {
                "transcript_key": "tk-a",
                "duration_seconds": 100,
                "word_count": 500,
                "speaker_count": 2,
                "analysis_completion": 50,
                "last_updated": "2024-01-01T00:00:00",
            },
            {
                "transcript_key": "tk-b",
                "duration_seconds": 200,
                "word_count": 1000,
                "speaker_count": 3,
                "analysis_completion": 75,
                "last_updated": "2024-01-02T00:00:00",
            },
        ]

        stats = StatisticsService.get_all_sessions_statistics()

        assert stats["total_transcripts"] == 2
        assert stats["total_sessions"] == 2
        assert stats["total_duration_seconds"] == 300
        assert stats["total_duration_minutes"] == 5.0  # 300 seconds / 60
        assert stats["total_word_count"] == 1500
        assert stats["total_speakers"] == 3  # max of speaker counts
        assert stats["average_completion"] == 62.5  # (50 + 75) / 2
        assert stats["total_artifact_bytes"] == 4096

    @patch("transcriptx.web.services.statistics_service.cached_list_available_sessions")
    @patch("transcriptx.web.services.statistics_service._total_artifact_bytes")
    def test_get_all_sessions_statistics_dedupes_by_transcript(
        self, mock_artifact_bytes, mock_list_sessions
    ):
        """Multiple runs for one transcript count once in aggregates."""
        mock_artifact_bytes.return_value = 0
        mock_list_sessions.return_value = [
            {
                "transcript_key": "tk-a",
                "name": "slug-a/run-2",
                "duration_seconds": 100,
                "word_count": 500,
                "speaker_count": 2,
                "analysis_completion": 80,
                "last_updated": "2024-01-02T00:00:00",
            },
            {
                "transcript_key": "tk-a",
                "name": "slug-a/run-1",
                "duration_seconds": 100,
                "word_count": 500,
                "speaker_count": 2,
                "analysis_completion": 40,
                "last_updated": "2024-01-01T00:00:00",
            },
            {
                "transcript_key": "tk-b",
                "name": "slug-b/run-1",
                "duration_seconds": 50,
                "word_count": 200,
                "speaker_count": 1,
                "analysis_completion": 100,
                "last_updated": "2024-01-03T00:00:00",
            },
        ]

        stats = StatisticsService.get_all_sessions_statistics()

        assert stats["total_transcripts"] == 2
        assert stats["total_sessions"] == 3
        assert stats["total_duration_seconds"] == 150
        assert stats["total_word_count"] == 700
        assert stats["average_completion"] == 90.0  # (80 + 100) / 2

    @patch("transcriptx.web.services.statistics_service.cached_list_available_sessions")
    @patch("transcriptx.web.services.statistics_service._total_artifact_bytes")
    def test_get_all_sessions_statistics_empty(
        self, mock_artifact_bytes, mock_list_sessions
    ):
        """Test getting statistics when no sessions exist."""
        mock_artifact_bytes.return_value = 0
        mock_list_sessions.return_value = []

        stats = StatisticsService.get_all_sessions_statistics()

        assert stats["total_transcripts"] == 0
        assert stats["total_sessions"] == 0
        assert stats["total_duration_seconds"] == 0
        assert stats["total_duration_minutes"] == 0
        assert stats["total_word_count"] == 0
        assert stats["average_completion"] == 0
        assert stats["total_artifact_bytes"] == 0

    def test_manifest_artifact_bytes_sums_declared_sizes(self, tmp_path: Path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        (run_dir / "manifest.json").write_text(
            '{"artifacts":[{"bytes":100},{"bytes":"50"},{"bytes":null},{}]}',
            encoding="utf-8",
        )
        assert _manifest_artifact_bytes(run_dir) == 150
        assert _manifest_artifact_bytes(tmp_path / "missing") == 0

    def test_total_artifact_bytes_includes_sessions_and_groups(
        self, tmp_path: Path, monkeypatch
    ):
        session_run = tmp_path / "slug" / "run-a"
        session_run.mkdir(parents=True)
        (session_run / "manifest.json").write_text(
            '{"artifacts":[{"bytes":1000}]}',
            encoding="utf-8",
        )
        group_run = tmp_path / "groups" / "g1" / "run-b"
        group_run.mkdir(parents=True)
        (group_run / "manifest.json").write_text(
            '{"artifacts":[{"bytes":250}]}',
            encoding="utf-8",
        )
        monkeypatch.setattr(
            "transcriptx.web.services.statistics_service.GROUP_OUTPUTS_DIR",
            tmp_path / "groups",
        )
        total = _total_artifact_bytes([{"path": str(session_run)}, {"path": None}])
        assert total == 1250
