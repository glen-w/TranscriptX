"""
Tests for common transcription utilities.

This module tests shared transcription functionality.
"""

from unittest.mock import patch, MagicMock


from transcriptx.cli.transcription_common import transcribe_with_whisperx


class TestTranscribeWithWhisperx:
    """Tests for transcribe_with_whisperx function."""

    def test_transcribes_audio_file(self, tmp_path):
        """Test that audio file is transcribed."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")

        config = MagicMock()

        with (
            patch(
                "transcriptx.cli.transcription_common.check_whisperx_compose_service"
            ) as mock_check,
            patch(
                "transcriptx.cli.transcription_common.run_whisperx_compose"
            ) as mock_transcribe,
            patch(
                "transcriptx.cli.transcription_common.wait_for_whisperx_service"
            ) as mock_wait,
        ):

            mock_check.return_value = True
            mock_wait.return_value = True
            mock_transcribe.return_value = str(tmp_path / "test.json")

            result = transcribe_with_whisperx(audio_file, config)

            assert result == str(tmp_path / "test.json")
            mock_transcribe.assert_called_once_with(audio_file, config)

    def test_starts_service_when_not_running(self, tmp_path):
        """Test that service is started when not running."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")

        config = MagicMock()

        with (
            patch(
                "transcriptx.cli.transcription_common.check_whisperx_compose_service"
            ) as mock_check,
            patch(
                "transcriptx.cli.transcription_common.start_whisperx_compose_service"
            ) as mock_start,
            patch(
                "transcriptx.cli.transcription_common.wait_for_whisperx_service"
            ) as mock_wait,
            patch(
                "transcriptx.cli.transcription_common.run_whisperx_compose"
            ) as mock_transcribe,
        ):

            mock_check.side_effect = [False, True]  # Not running, then running
            mock_start.return_value = True
            mock_wait.return_value = True
            mock_transcribe.return_value = str(tmp_path / "test.json")

            result = transcribe_with_whisperx(audio_file, config)

            assert result is not None
            mock_start.assert_called_once()

    def test_returns_none_when_service_start_fails(self, tmp_path):
        """Test that None is returned when service start fails."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")

        config = MagicMock()

        with (
            patch(
                "transcriptx.cli.transcription_common.check_whisperx_compose_service"
            ) as mock_check,
            patch(
                "transcriptx.cli.transcription_common.start_whisperx_compose_service"
            ) as mock_start,
        ):

            mock_check.return_value = False
            mock_start.return_value = False

            result = transcribe_with_whisperx(audio_file, config)

            assert result is None

    def test_waits_for_service_stability(self, tmp_path):
        """Test that service stability is waited for."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")

        config = MagicMock()

        with (
            patch(
                "transcriptx.cli.transcription_common.check_whisperx_compose_service"
            ) as mock_check,
            patch(
                "transcriptx.cli.transcription_common.wait_for_whisperx_service"
            ) as mock_wait,
            patch(
                "transcriptx.cli.transcription_common.run_whisperx_compose"
            ) as mock_transcribe,
        ):

            mock_check.return_value = True
            mock_wait.return_value = True
            mock_transcribe.return_value = str(tmp_path / "test.json")

            transcribe_with_whisperx(audio_file, config)

            mock_wait.assert_called()

    def test_returns_none_when_transcription_fails(self, tmp_path):
        """Test that None is returned when transcription fails."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")

        config = MagicMock()

        with (
            patch(
                "transcriptx.cli.transcription_common.check_whisperx_compose_service"
            ) as mock_check,
            patch(
                "transcriptx.cli.transcription_common.wait_for_whisperx_service"
            ) as mock_wait,
            patch(
                "transcriptx.cli.transcription_common.run_whisperx_compose"
            ) as mock_transcribe,
        ):

            mock_check.return_value = True
            mock_wait.return_value = True
            mock_transcribe.return_value = None

            result = transcribe_with_whisperx(audio_file, config)

            assert result is None

    def test_handles_exceptions(self, tmp_path):
        """Test that exceptions are handled gracefully."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")

        config = MagicMock()

        with (
            patch(
                "transcriptx.cli.transcription_common.check_whisperx_compose_service"
            ) as mock_check,
            patch("transcriptx.cli.transcription_common.log_error") as mock_log,
        ):

            mock_check.side_effect = Exception("Test error")

            result = transcribe_with_whisperx(audio_file, config)

            assert result is None
            mock_log.assert_called()
