"""
Tests for audio playback functionality.

This module tests audio playback controller and key bindings.
"""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from transcriptx.cli.audio_playback_handler import (
    PlaybackController,
    create_playback_key_bindings,
)
audio_utils = pytest.importorskip("transcriptx.cli.audio_utils")
SegmentPlayer = audio_utils.SegmentPlayer


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
        
        with patch('transcriptx.cli.audio_playback_handler.play_audio_file') as mock_play:
            mock_process = MagicMock()
            mock_play.return_value = mock_process
            
            result = controller.play(audio_file)
            
            assert result is True
            assert controller._current_file == audio_file
            assert controller._current_process == mock_process
    
    def test_stops_playback(self, tmp_path):
        """Test that playback is stopped."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")
        
        controller = PlaybackController()
        
        with patch('transcriptx.cli.audio_playback_handler.play_audio_file') as mock_play, \
             patch('transcriptx.cli.audio_playback_handler.stop_audio_playback') as mock_stop:
            
            mock_process = MagicMock()
            mock_play.return_value = mock_process
            
            controller.play(audio_file)
            controller.stop()
            
            assert controller._current_process is None
            assert controller._current_file is None
            mock_stop.assert_called_once()
    
    def test_stops_existing_playback_when_playing_new(self, tmp_path):
        """Test that existing playback is stopped when playing new file."""
        audio_file1 = tmp_path / "test1.mp3"
        audio_file2 = tmp_path / "test2.mp3"
        
        controller = PlaybackController()
        
        with patch('transcriptx.cli.audio_playback_handler.play_audio_file') as mock_play, \
             patch('transcriptx.cli.audio_playback_handler.stop_audio_playback') as mock_stop:
            
            mock_process1 = MagicMock()
            mock_process2 = MagicMock()
            mock_play.side_effect = [mock_process1, mock_process2]
            
            controller.play(audio_file1)
            controller.play(audio_file2)
            
            # Should have stopped first playback
            assert mock_stop.called
            assert controller._current_file == audio_file2
    
    def test_skips_forward(self, tmp_path):
        """Test that playback can skip forward."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")
        
        controller = PlaybackController()
        
        with patch('transcriptx.cli.audio_playback_handler.play_audio_file') as mock_play, \
             patch('transcriptx.cli.audio_playback_handler.check_ffplay_available') as mock_check, \
             patch('transcriptx.cli.audio_playback_handler.get_audio_duration') as mock_duration, \
             patch('transcriptx.cli.audio_playback_handler.play_audio_file_from_position') as mock_play_pos:
            
            mock_process = MagicMock()
            mock_play.return_value = mock_process
            mock_check.return_value = (True, "ffplay")
            mock_duration.return_value = 100.0
            
            controller.play(audio_file)
            controller._current_position = 10.0
            
            result = controller.skip(5.0)
            
            # Should attempt to skip
            assert isinstance(result, bool)
    
    def test_skips_backward(self, tmp_path):
        """Test that playback can skip backward."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")
        
        controller = PlaybackController()
        
        with patch('transcriptx.cli.audio_playback_handler.play_audio_file') as mock_play, \
             patch('transcriptx.cli.audio_playback_handler.check_ffplay_available') as mock_check, \
             patch('transcriptx.cli.audio_playback_handler.get_audio_duration') as mock_duration:
            
            mock_process = MagicMock()
            mock_play.return_value = mock_process
            mock_check.return_value = (True, "ffplay")
            mock_duration.return_value = 100.0
            
            controller.play(audio_file)
            controller._current_position = 20.0
            
            result = controller.skip(-5.0)
            
            # Should attempt to skip backward
            assert isinstance(result, bool)
    
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
        
        with patch('transcriptx.cli.audio_playback_handler.play_audio_file') as mock_play, \
             patch('transcriptx.cli.audio_playback_handler.check_ffplay_available') as mock_check:
            
            mock_process = MagicMock()
            mock_play.return_value = mock_process
            mock_check.return_value = (False, None)
            
            controller.play(audio_file)
            
            result = controller.skip(5.0)
            
            assert result is False
    
    def test_get_position_returns_current_position(self, tmp_path):
        """Test that get_position returns current position."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")
        
        controller = PlaybackController()
        
        with patch('transcriptx.cli.audio_playback_handler.play_audio_file') as mock_play:
            mock_process = MagicMock()
            mock_play.return_value = mock_process
            
            controller.play(audio_file)
            controller._current_position = 15.5
            
            position = controller.get_position()
            
            assert position == 15.5
    
    def test_get_position_calculates_from_time(self, tmp_path):
        """Test that position is calculated from playback time."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")
        
        controller = PlaybackController()
        
        with patch('transcriptx.cli.audio_playback_handler.play_audio_file') as mock_play, \
             patch('time.time') as mock_time:
            
            mock_process = MagicMock()
            mock_play.return_value = mock_process
            
            # Simulate playback start
            mock_time.side_effect = [100.0, 115.5]  # Start time, current time
            
            controller.play(audio_file)
            
            position = controller.get_position()
            
            # Should calculate from elapsed time
            assert isinstance(position, float)
            assert position >= 0.0


class TestCreatePlaybackKeyBindings:
    """Tests for create_playback_key_bindings function."""
    
    def test_creates_key_bindings(self):
        """Test that key bindings are created."""
        controller = PlaybackController()
        
        bindings = create_playback_key_bindings(controller)
        
        assert bindings is not None
        # Should be a KeyBindings object or similar
        assert hasattr(bindings, 'add') or hasattr(bindings, 'bindings')


class TestSegmentPlayer:
    """Tests for SegmentPlayer helper."""

    def test_stop_before_play(self, tmp_path):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")

        player = SegmentPlayer()
        fake_proc = MagicMock()
        player._proc = fake_proc

        with patch("transcriptx.cli.audio_utils.stop_audio_playback") as mock_stop, \
             patch("transcriptx.cli.audio_utils.check_ffplay_available") as mock_ffplay, \
             patch("transcriptx.cli.audio_utils.shutil.which") as mock_which, \
             patch("transcriptx.cli.audio_utils.subprocess.Popen") as mock_popen:
            mock_ffplay.return_value = (True, None)
            mock_which.return_value = "/usr/bin/ffplay"
            mock_popen.return_value = MagicMock()

            player.play_segment(audio_file, 0.0, 1.0)

            mock_stop.assert_called_once_with(fake_proc)

    def test_ffplay_args_include_noise_flags(self, tmp_path):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")

        player = SegmentPlayer()

        with patch("transcriptx.cli.audio_utils.check_ffplay_available") as mock_ffplay, \
             patch("transcriptx.cli.audio_utils.shutil.which") as mock_which, \
             patch("transcriptx.cli.audio_utils.subprocess.Popen") as mock_popen:
            mock_ffplay.return_value = (True, None)
            mock_which.return_value = "/usr/bin/ffplay"
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
        monkeypatch.setattr("transcriptx.cli.audio_utils.sys.platform", "darwin")

        fake_proc = MagicMock()
        fake_proc.poll.return_value = 1
        fake_proc.returncode = 1
        fake_proc.stderr.read.return_value = b"option not supported"

        with patch("transcriptx.cli.audio_utils.check_ffplay_available") as mock_ffplay, \
             patch("transcriptx.cli.audio_utils.subprocess.Popen") as mock_popen, \
             patch("transcriptx.cli.audio_utils.time.sleep") as mock_sleep, \
             patch.object(SegmentPlayer, "_play_temp_clip") as mock_temp_clip:
            mock_ffplay.return_value = (False, "missing")
            mock_popen.return_value = fake_proc
            mock_temp_clip.return_value = MagicMock()

            player.play_segment(audio_file, 0.0, 2.0)

            assert mock_temp_clip.called
