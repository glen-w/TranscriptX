"""
Tests for audio playback functionality.

This module tests audio playback controller and key bindings.
"""

from unittest.mock import patch, MagicMock

import pytest

from transcriptx.cli.audio_playback_handler import (
    PlaybackController,
    create_playback_key_bindings,
)

from transcriptx.cli.audio import SegmentPlayer


class TestPlaybackController:
    """Tests for PlaybackController class."""

    def test_initialization(self):
        """Test PlaybackController initialization."""
        controller = PlaybackController()

        assert controller._current_process is None
        assert controller._current_file is None
        assert controller._current_position == 0.0

    def test_plays_audio_file(self, tmp_path):
        """Test that audio file playback is started."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")

        controller = PlaybackController()
        mock_process = MagicMock()

        with patch(
            "transcriptx.cli.audio.playback.play_audio_file",
            return_value=mock_process,
        ):
            result = controller.play(audio_file)

        assert result is True
        assert controller._current_file == audio_file
        assert controller._current_process == mock_process

    def test_stops_playback(self, tmp_path):
        """Test that playback is stopped."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")

        controller = PlaybackController()
        mock_process = MagicMock()

        with (
            patch(
                "transcriptx.cli.audio.playback.play_audio_file",
                return_value=mock_process,
            ),
            patch(
                "transcriptx.cli.audio_playback_handler.stop_audio_playback"
            ) as mock_stop,
        ):
            controller.play(audio_file)
            controller.stop()

        assert controller._current_process is None
        assert controller._current_file is None
        mock_stop.assert_called_once()

    def test_stops_existing_playback_when_playing_new(self, tmp_path):
        """Test that existing playback is stopped when playing new file."""
        audio_file1 = tmp_path / "test1.mp3"
        audio_file2 = tmp_path / "test2.mp3"
        audio_file1.write_text("fake1")
        audio_file2.write_text("fake2")

        controller = PlaybackController()
        mock_process1 = MagicMock()
        mock_process2 = MagicMock()

        with (
            patch(
                "transcriptx.cli.audio.playback.play_audio_file",
                side_effect=[mock_process1, mock_process2],
            ),
            patch(
                "transcriptx.cli.audio_playback_handler.stop_audio_playback"
            ) as mock_stop,
        ):
            controller.play(audio_file1)
            controller.play(audio_file2)

        assert mock_stop.called
        assert controller._current_file == audio_file2

    def test_skips_forward(self, tmp_path):
        """Test that playback can skip forward."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")

        controller = PlaybackController()
        mock_process = MagicMock()

        with (
            patch(
                "transcriptx.cli.audio.playback.play_audio_file",
                return_value=mock_process,
            ),
            patch(
                "transcriptx.cli.audio_playback_handler.check_ffplay_available",
                return_value=(True, None),
            ),
            patch(
                "transcriptx.cli.audio_playback_handler.get_audio_duration",
                return_value=60.0,
            ),
            patch(
                "transcriptx.cli.audio_playback_handler.play_audio_file_from_position",
                return_value=MagicMock(),
            ),
        ):
            controller.play(audio_file)
            controller._current_position = 10.0

            result = controller.skip(5.0)

            assert result is True

    def test_skips_backward(self, tmp_path):
        """Test that playback can skip backward."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")

        controller = PlaybackController()

        with (
            patch(
                "transcriptx.cli.audio.playback.play_audio_file",
                return_value=MagicMock(),
            ),
            patch(
                "transcriptx.cli.audio_playback_handler.check_ffplay_available",
                return_value=(True, None),
            ),
            patch(
                "transcriptx.cli.audio_playback_handler.get_audio_duration",
                return_value=100.0,
            ),
            patch(
                "transcriptx.cli.audio_playback_handler.play_audio_file_from_position",
                return_value=MagicMock(),
            ),
        ):
            controller.play(audio_file)
            controller._current_position = 20.0

            result = controller.skip(-5.0)

            assert result is True

    def test_returns_false_when_no_file_playing(self):
        """Test that skip returns False when no file is playing."""
        controller = PlaybackController()

        result = controller.skip(5.0)

        assert result is False

    def test_returns_false_when_ffplay_not_available(self, tmp_path):
        """Test that skip returns False when ffplay is not available."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")

        controller = PlaybackController()

        with (
            patch(
                "transcriptx.cli.audio.playback.play_audio_file",
                return_value=MagicMock(),
            ),
            patch(
                "transcriptx.cli.audio_playback_handler.check_ffplay_available",
                return_value=(False, "not available"),
            ),
        ):
            controller.play(audio_file)
            result = controller.skip(5.0)

        assert result is False

    def test_get_position_returns_current_position(self, tmp_path):
        """Test that get_position returns current position."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")

        controller = PlaybackController()

        with patch(
            "transcriptx.cli.audio.playback.play_audio_file",
            return_value=MagicMock(),
        ):
            controller.play(audio_file)
            controller._current_position = 15.5

            position = controller.get_position()

            assert position == pytest.approx(15.5)

    def test_get_position_calculates_from_time(self, tmp_path):
        """Test that position is calculated from playback time."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")

        controller = PlaybackController()

        with (
            patch(
                "transcriptx.cli.audio.playback.play_audio_file",
                return_value=MagicMock(),
            ),
            patch("time.time", side_effect=[100.0, 115.5]),
        ):
            controller.play(audio_file)

            position = controller.get_position()

            assert isinstance(position, float)
            assert position >= 0.0


class TestCreatePlaybackKeyBindings:
    """Tests for create_playback_key_bindings function."""

    def test_creates_key_bindings(self):
        """Test that key bindings are created."""
        controller = PlaybackController()
        get_current_file = lambda: None

        bindings = create_playback_key_bindings(controller, get_current_file)

        assert bindings is not None
        assert hasattr(bindings, "add") or hasattr(bindings, "bindings")


class TestSegmentPlayer:
    """Tests for SegmentPlayer helper."""

    def test_stop_before_play(self, tmp_path):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")

        player = SegmentPlayer()
        fake_proc = MagicMock()
        player._proc = fake_proc

        with (
            patch(
                "transcriptx.cli.audio.playback.stop_audio_playback"
            ) as mock_stop,
            patch(
                "transcriptx.cli.audio.playback.check_ffplay_available",
                return_value=(True, None),
            ),
            patch(
                "transcriptx.cli.audio.playback.shutil.which",
                return_value="/usr/bin/ffplay",
            ),
            patch(
                "transcriptx.cli.audio.playback.subprocess.Popen",
                return_value=MagicMock(),
            ),
        ):
            player.play_segment(audio_file, 0.0, 1.0)

            mock_stop.assert_called_once_with(fake_proc)

    def test_ffplay_args_include_noise_flags(self, tmp_path):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")

        player = SegmentPlayer()

        with (
            patch(
                "transcriptx.cli.audio.playback.check_ffplay_available",
                return_value=(True, None),
            ),
            patch(
                "transcriptx.cli.audio.playback.shutil.which",
                return_value="/usr/bin/ffplay",
            ),
            patch(
                "transcriptx.cli.audio.playback.subprocess.Popen"
            ) as mock_popen,
        ):
            mock_popen.return_value = MagicMock()

            player.play_segment(audio_file, 1.0, 2.0)

            args = mock_popen.call_args[0][0]
            assert "-nostats" in args
            assert "-loglevel" in args
            assert "error" in args

    def test_afplay_failure_falls_back_to_temp_clip(self, tmp_path, monkeypatch):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")

        player = SegmentPlayer()
        monkeypatch.setattr(
            "transcriptx.cli.audio.playback.sys.platform", "darwin"
        )

        fake_proc = MagicMock()
        fake_proc.poll.return_value = 1
        fake_proc.returncode = 1
        fake_proc.stderr.read.return_value = b"option not supported"

        with (
            patch(
                "transcriptx.cli.audio.playback.check_ffplay_available",
                return_value=(False, "missing"),
            ),
            patch(
                "transcriptx.cli.audio.playback.subprocess.Popen",
                return_value=fake_proc,
            ),
            patch("transcriptx.cli.audio.playback.time.sleep"),
            patch.object(SegmentPlayer, "_play_temp_clip") as mock_temp_clip,
        ):
            mock_temp_clip.return_value = MagicMock()

            player.play_segment(audio_file, 0.0, 2.0)

            assert mock_temp_clip.called
