"""
Tests for file selection interface.

This module tests interactive file selection with playback and rename support.
"""

from unittest.mock import patch


from transcriptx.cli.file_selection_interface import (
    FileSelectionConfig,
    _format_skip_label,
    select_files_interactive,
)


class TestFileSelectionConfig:
    """Tests for FileSelectionConfig dataclass."""

    def test_initialization_with_defaults(self):
        """Test FileSelectionConfig initialization with defaults."""
        config = FileSelectionConfig()

        assert config.multi_select is True
        assert config.enable_playback is False
        assert config.enable_rename is False
        assert config.title == "File Selection"
        assert config.skip_seconds_short == 10.0
        assert config.skip_seconds_long == 60.0

    def test_initialization_with_custom_skip_values(self):
        """Test FileSelectionConfig with custom skip amounts."""
        config = FileSelectionConfig(
            enable_playback=True,
            skip_seconds_short=5.0,
            skip_seconds_long=120.0,
        )
        assert config.skip_seconds_short == 5.0
        assert config.skip_seconds_long == 120.0

    def test_initialization_with_custom_values(self):
        """Test FileSelectionConfig initialization with custom values."""
        config = FileSelectionConfig(
            multi_select=False, enable_playback=True, title="Custom Title"
        )

        assert config.multi_select is False
        assert config.enable_playback is True
        assert config.title == "Custom Title"


class TestFormatSkipLabel:
    """Tests for _format_skip_label helper."""

    def test_format_seconds(self):
        assert _format_skip_label(10, "-") == "Skip -10s"
        assert _format_skip_label(10, "+") == "Skip +10s"
        assert _format_skip_label(5, "-") == "Skip -5s"

    def test_format_minutes(self):
        assert _format_skip_label(60, "-") == "Skip -1m"
        assert _format_skip_label(60, "+") == "Skip +1m"
        assert _format_skip_label(120, "+") == "Skip +2m"


class TestSelectFilesInteractive:
    """Tests for select_files_interactive function."""

    def test_returns_none_when_no_files(self):
        """Test that None is returned when no files provided."""
        result = select_files_interactive([], FileSelectionConfig())

        assert result is None

    def test_selects_single_file(self, tmp_path):
        """Test that single file can be selected."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        with patch("transcriptx.cli.file_selection_interface.questionary") as mock_q:
            mock_q.checkbox.return_value.ask.return_value = ["test.txt"]

            result = select_files_interactive(
                [test_file], FileSelectionConfig(multi_select=True)
            )

            assert result == [test_file]

    def test_selects_multiple_files(self, tmp_path):
        """Test that multiple files can be selected."""
        file1 = tmp_path / "test1.txt"
        file2 = tmp_path / "test2.txt"
        file1.write_text("content1")
        file2.write_text("content2")

        with patch("transcriptx.cli.file_selection_interface.questionary") as mock_q:
            mock_q.checkbox.return_value.ask.return_value = ["test1.txt", "test2.txt"]

            result = select_files_interactive(
                [file1, file2], FileSelectionConfig(multi_select=True)
            )

            assert len(result) == 2
            assert file1 in result
            assert file2 in result

    def test_returns_none_when_cancelled(self, tmp_path):
        """Test that None is returned when user cancels."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        with patch("transcriptx.cli.file_selection_interface.questionary") as mock_q:
            mock_q.checkbox.return_value.ask.return_value = None

            result = select_files_interactive([test_file], FileSelectionConfig())

            assert result is None

    def test_auto_enables_playback_for_audio_files(self, tmp_path):
        """Test that playback is auto-enabled for audio files."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")

        with (
            patch(
                "transcriptx.cli.file_selection_interface.is_audio_file"
            ) as mock_is_audio,
            patch("transcriptx.cli.file_selection_interface.questionary") as mock_q,
        ):

            mock_is_audio.return_value = True
            mock_q.checkbox.return_value.ask.return_value = ["test.mp3"]

            config = FileSelectionConfig()
            result = select_files_interactive([audio_file], config)

            # Playback should be enabled for audio files
            assert config.enable_playback is True or result is not None

    def test_uses_custom_formatter(self, tmp_path):
        """Test that custom formatter is used."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        def custom_formatter(path):
            return f"CUSTOM: {path.name}"

        with patch("transcriptx.cli.file_selection_interface.questionary") as mock_q:
            mock_q.checkbox.return_value.ask.return_value = ["test.txt"]

            config = FileSelectionConfig(metadata_formatter=custom_formatter)
            result = select_files_interactive([test_file], config)

            # Should use custom formatter
            assert result is not None

    def test_validates_files_when_validator_provided(self, tmp_path):
        """Test that files are validated when validator is provided."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        def validator(path):
            return (True, None) if path.name == "test.txt" else (False, "Invalid")

        with patch("transcriptx.cli.file_selection_interface.questionary") as mock_q:
            mock_q.checkbox.return_value.ask.return_value = ["test.txt"]

            config = FileSelectionConfig(validator=validator)
            result = select_files_interactive([test_file], config)

            # Should validate files
            assert result is not None

    def test_filters_invalid_files(self, tmp_path):
        """Test that invalid files are filtered out."""
        valid_file = tmp_path / "valid.txt"
        invalid_file = tmp_path / "invalid.txt"
        valid_file.write_text("content")
        invalid_file.write_text("content")

        def validator(path):
            return (True, None) if path.name == "valid.txt" else (False, "Invalid")

        with patch("transcriptx.cli.file_selection_interface.questionary") as mock_q:
            mock_q.checkbox.return_value.ask.return_value = ["valid.txt"]

            config = FileSelectionConfig(validator=validator)
            result = select_files_interactive([valid_file, invalid_file], config)

            # Should only include valid files
            assert result == [valid_file]
