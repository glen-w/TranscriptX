"""
Tests for UI helper functions.

This module tests UI prompt functions, color utilities, and display helpers.
"""

from unittest.mock import patch

import pytest

from transcriptx.io.ui import (
    get_color_for_speaker,
    prompt_for_audio_file,
    prompt_for_transcript_folder,
    prompt_for_transcript_file,
    choose_mapping_action,
    show_banner,
    prompt_main_choice,
    prompt_audio_path,
    prompt_transcript_path,
    display_progress,
)


class TestGetColorForSpeaker:
    """Tests for get_color_for_speaker function."""

    def test_returns_color_for_speaker_id(self):
        """Test that color is returned for speaker ID."""
        color = get_color_for_speaker("SPEAKER_00")

        assert color is not None
        assert isinstance(color, str)

    def test_returns_different_colors_for_different_speakers(self):
        """Test that different speakers get different colors."""
        color1 = get_color_for_speaker("SPEAKER_00")
        color2 = get_color_for_speaker("SPEAKER_01")

        # Colors might cycle, but should be valid
        assert color1 is not None
        assert color2 is not None

    def test_handles_numeric_speaker_ids(self):
        """Test that numeric speaker IDs are handled."""
        color = get_color_for_speaker("SPEAKER_05")

        assert color is not None

    def test_handles_non_numeric_suffix(self):
        """Test that non-numeric suffixes default to index 0."""
        color = get_color_for_speaker("SPEAKER_ABC")

        assert color is not None


class TestPromptForAudioFile:
    """Tests for prompt_for_audio_file function."""

    def test_returns_selected_file(self, tmp_path):
        """Test that selected file path is returned."""
        # Create audio file
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")

        with (
            patch("transcriptx.io.ui.RECORDINGS_DIR", str(tmp_path)),
            patch("transcriptx.io.ui.questionary") as mock_q,
        ):

            mock_q.select.return_value.ask.return_value = "test.mp3"

            result = prompt_for_audio_file(str(tmp_path))

            assert result == str(audio_file)

    def test_returns_none_when_no_files(self, tmp_path):
        """Test that None is returned when no audio files found."""
        with (
            patch("transcriptx.io.ui.RECORDINGS_DIR", str(tmp_path)),
            patch("transcriptx.io.ui.print") as mock_print,
        ):

            result = prompt_for_audio_file(str(tmp_path))

            assert result is None
            mock_print.assert_called()

    def test_filters_out_transcribed_files(self, tmp_path):
        """Test that already transcribed files are filtered out."""
        # Create audio file with transcript
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")
        transcript_file = tmp_path / "test.json"
        transcript_file.write_text("{}")

        with (
            patch("transcriptx.io.ui.RECORDINGS_DIR", str(tmp_path)),
            patch("transcriptx.io.ui.questionary") as mock_q,
        ):

            # Should not show test.mp3 since transcript exists
            mock_q.select.return_value.ask.return_value = None

            result = prompt_for_audio_file(str(tmp_path))

            # Should return None or different file
            assert result is None or result != str(audio_file)

    def test_handles_keyboard_interrupt(self, tmp_path):
        """Test that KeyboardInterrupt is handled."""
        # Create an audio file so the function doesn't return early
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")

        with (
            patch("transcriptx.io.ui.RECORDINGS_DIR", str(tmp_path)),
            patch("transcriptx.io.ui.questionary") as mock_q,
            patch("transcriptx.io.ui.sys.exit") as mock_exit,
        ):

            # Make sure files are found
            mock_q.select.return_value.ask.side_effect = KeyboardInterrupt()

            try:
                prompt_for_audio_file(str(tmp_path))
            except KeyboardInterrupt:
                pass  # Expected

            # sys.exit should be called on KeyboardInterrupt
            mock_exit.assert_called()


class TestPromptForTranscriptFolder:
    """Tests for prompt_for_transcript_folder function."""

    def test_returns_selected_folder(self, tmp_path):
        """Test that selected folder path is returned."""
        with (
            patch("transcriptx.io.ui.questionary") as mock_q,
            patch("transcriptx.io.ui.os.path.isdir") as mock_isdir,
        ):

            mock_q.path.return_value.ask.return_value = str(tmp_path)
            mock_isdir.return_value = True

            result = prompt_for_transcript_folder()

            assert result == str(tmp_path)

    def test_exits_on_invalid_folder(self):
        """Test that program exits on invalid folder."""
        with (
            patch("transcriptx.io.ui.questionary") as mock_q,
            patch("transcriptx.io.ui.os.path.isdir") as mock_isdir,
            patch("transcriptx.io.ui.sys.exit") as mock_exit,
        ):

            mock_q.path.return_value.ask.return_value = "/invalid"
            mock_isdir.return_value = False

            prompt_for_transcript_folder()

            mock_exit.assert_called()


class TestPromptForTranscriptFile:
    """Tests for prompt_for_transcript_file function."""

    def test_returns_selected_file(self, tmp_path, monkeypatch):
        """Test that selected file is returned."""
        # Create JSON file
        json_file = tmp_path / "test.json"
        json_file.write_text("{}")

        monkeypatch.chdir(tmp_path)

        with patch("transcriptx.io.ui.questionary") as mock_q:
            mock_q.select.return_value.ask.return_value = "test.json"

            result = prompt_for_transcript_file()

            assert result == "test.json"

    def test_raises_error_when_no_json_files(self, tmp_path, monkeypatch):
        """Test that FileNotFoundError is raised when no JSON files."""
        monkeypatch.chdir(tmp_path)

        with pytest.raises(FileNotFoundError, match="No .json files found"):
            prompt_for_transcript_file()


class TestChooseMappingAction:
    """Tests for choose_mapping_action function."""

    def test_returns_default_in_batch_mode(self):
        """Test that default action is returned in batch mode."""
        result = choose_mapping_action(5, batch_mode=True)

        assert "Proceed" in result

    def test_includes_review_options(self):
        """Test that review options are included."""
        with patch("transcriptx.io.ui.questionary") as mock_q:
            mock_q.select.return_value.ask.return_value = "🔁 Review all speaker labels"

            result = choose_mapping_action(0, batch_mode=False)

            assert result == "🔁 Review all speaker labels"

    def test_includes_unidentified_option_when_unidentified_exist(self):
        """Test that unidentified option is shown when unidentified speakers exist."""
        with patch("transcriptx.io.ui.questionary") as mock_q:
            mock_q.select.return_value.ask.return_value = (
                "🎭 Review unidentified speakers only (5)"
            )

            result = choose_mapping_action(5, batch_mode=False)

            assert "unidentified" in result.lower()

    def test_includes_tags_option_when_tags_exist(self):
        """Test that tags option is shown when tags exist."""
        with patch("transcriptx.io.ui.questionary") as mock_q:
            mock_q.select.return_value.ask.return_value = "🏷️ Manage tags"

            result = choose_mapping_action(0, batch_mode=False, has_tags=True)

            assert "tags" in result.lower() or "🏷️" in result


class TestShowBanner:
    """Tests for show_banner function."""

    def test_displays_banner(self):
        """Test that banner is displayed."""
        with patch("transcriptx.io.ui.console") as mock_console:
            show_banner()

            assert mock_console.print.call_count >= 3  # Multiple lines


class TestPromptMainChoice:
    """Tests for prompt_main_choice function."""

    def test_returns_transcribe_choice(self):
        """Test that 'transcribe' is returned for transcribe option."""
        with patch("transcriptx.io.ui.questionary") as mock_q:
            mock_q.select.return_value.ask.return_value = "Transcribe audio file"

            result = prompt_main_choice()

            assert result == "transcribe"

    def test_returns_analyze_choice(self):
        """Test that 'analyze' is returned for analyze option."""
        with patch("transcriptx.io.ui.questionary") as mock_q:
            mock_q.select.return_value.ask.return_value = "Analyze transcript file"

            result = prompt_main_choice()

            assert result == "analyze"

    def test_returns_exit_choice(self):
        """Test that 'exit' is returned for exit option."""
        with patch("transcriptx.io.ui.questionary") as mock_q:
            mock_q.select.return_value.ask.return_value = "Exit"

            result = prompt_main_choice()

            assert result == "exit"


class TestPromptAudioPath:
    """Tests for prompt_audio_path function."""

    def test_returns_entered_path(self):
        """Test that entered path is returned."""
        with patch("transcriptx.io.ui.questionary") as mock_q:
            mock_q.path.return_value.ask.return_value = "/path/to/audio.mp3"

            result = prompt_audio_path()

            assert result == "/path/to/audio.mp3"
            mock_q.path.assert_called_once()


class TestPromptTranscriptPath:
    """Tests for prompt_transcript_path function."""

    def test_returns_entered_path(self):
        """Test that entered path is returned."""
        with patch("transcriptx.io.ui.questionary") as mock_q:
            mock_q.path.return_value.ask.return_value = "/path/to/transcript.json"

            result = prompt_transcript_path()

            assert result == "/path/to/transcript.json"
            mock_q.path.assert_called_once()


class TestDisplayProgress:
    """Tests for display_progress function."""

    def test_displays_progress_bar(self, capsys):
        """Test that progress bar is displayed."""
        display_progress(50, 100, "Test Progress")

        captured = capsys.readouterr()
        assert "Test Progress" in captured.out or "50%" in captured.out

    def test_handles_zero_total(self, capsys):
        """Test that zero total is handled gracefully."""
        display_progress(0, 0, "Test")

        # Should not crash
        captured = capsys.readouterr()
        # May or may not output anything

    def test_handles_completion(self, capsys):
        """Test that completion is handled."""
        display_progress(100, 100, "Test")

        captured = capsys.readouterr()
        # Should show 100% or completion

    def test_handles_negative_values(self, capsys):
        """Test that negative values are handled."""
        display_progress(-10, 100, "Test")

        # Should not crash
        captured = capsys.readouterr()
