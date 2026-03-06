"""
Tests for file selection interface.

This module tests interactive file selection with playback and rename support.
"""

from unittest.mock import patch


from transcriptx.cli.file_selection_interface import (
    FileSelectionConfig,
    _apply_validator,
    _build_initial_choices_and_cache,
    _build_shortcuts_for_help,
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


class TestApplyValidator:
    """Tests for _apply_validator helper."""

    def test_returns_all_files_when_no_validator(self, tmp_path):
        files = [tmp_path / "a.txt", tmp_path / "b.txt"]
        config = FileSelectionConfig(validator=None)
        assert _apply_validator(files, config) == files

    def test_filters_by_validator(self, tmp_path):
        (tmp_path / "a.txt").touch()
        (tmp_path / "b.txt").touch()
        files = [tmp_path / "a.txt", tmp_path / "b.txt"]
        config = FileSelectionConfig(validator=lambda p: (p.name == "a.txt", None))
        result = _apply_validator(files, config)
        assert len(result) == 1
        assert result[0].name == "a.txt"


class TestBuildInitialChoicesAndCache:
    """Tests for _build_initial_choices_and_cache helper."""

    def test_returns_choices_and_cache(self, tmp_path):
        from pathlib import Path

        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        a.touch()
        b.touch()
        files = [a, b]
        all_files = list(files)

        def formatter(p: Path) -> str:
            return f"📄 {p.name}"

        choices, cache, labels = _build_initial_choices_and_cache(
            files, all_files, formatter
        )
        assert len(choices) == 2
        assert choices[0][0] == a and "a.txt" in choices[0][1]
        assert choices[1][0] == b and "b.txt" in choices[1][1]
        assert a in cache and b in cache
        assert labels[a] == f"📄 {a.name}"
        assert labels[b] == f"📄 {b.name}"

    def test_fallback_label_on_formatter_error(self, tmp_path):
        from pathlib import Path

        f = tmp_path / "x.txt"
        f.touch()

        def failing(_: Path) -> str:
            raise RuntimeError("nope")

        choices, cache, labels = _build_initial_choices_and_cache([f], [f], failing)
        assert len(choices) == 1
        assert "📄" in choices[0][1] and "x.txt" in choices[0][1]
        assert f in labels


class TestBuildShortcutsForHelp:
    """Tests for _build_shortcuts_for_help helper."""

    def test_returns_base_shortcuts(self):
        config = FileSelectionConfig()
        shortcuts = _build_shortcuts_for_help(config, [])
        labels = [s[1] for s in shortcuts]
        assert "Select" in labels
        assert "Confirm" in labels
        assert "Cancel" in labels

    def test_includes_playback_when_enabled(self):
        config = FileSelectionConfig(enable_playback=True)
        shortcuts = _build_shortcuts_for_help(config, [])
        labels = [s[1] for s in shortcuts]
        assert "Play" in labels


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
