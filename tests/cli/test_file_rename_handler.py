"""
Tests for file rename handler.

This module tests filename validation and interactive renaming.
"""

from unittest.mock import patch


from transcriptx.cli.file_rename_handler import (
    validate_filename,
    perform_rename,
    rename_file_interactive,
)


class TestValidateFilename:
    """Tests for validate_filename function."""

    def test_validates_valid_filename(self):
        """Test that valid filename passes validation."""
        is_valid, error = validate_filename("test_file.json")

        assert is_valid is True
        assert error is None

    def test_rejects_empty_filename(self):
        """Test that empty filename is rejected."""
        is_valid, error = validate_filename("")

        assert is_valid is False
        assert error is not None
        assert "empty" in error.lower()

    def test_rejects_whitespace_only(self):
        """Test that whitespace-only filename is rejected."""
        is_valid, error = validate_filename("   ")

        assert is_valid is False
        assert error is not None

    def test_rejects_invalid_characters(self):
        """Test that invalid characters are rejected."""
        invalid_chars = ["/", "\\", ":", "*", "?", '"', "<", ">", "|"]

        for char in invalid_chars:
            is_valid, error = validate_filename(f"test{char}file.json")

            assert is_valid is False
            assert error is not None
            assert "Invalid characters" in error


class TestPerformRename:
    """Tests for perform_rename function."""

    def test_renames_file_successfully(self, tmp_path):
        """Test that file is renamed successfully."""
        old_file = tmp_path / "old_name.txt"
        old_file.write_text("content")

        success, new_path = perform_rename(old_file, "new_name.txt")

        assert success is True
        assert new_path == tmp_path / "new_name.txt"
        assert new_path.exists()
        assert not old_file.exists()

    def test_returns_false_when_file_not_exists(self, tmp_path):
        """Test that False is returned when file doesn't exist."""
        old_file = tmp_path / "nonexistent.txt"

        success, new_path = perform_rename(old_file, "new_name.txt")

        assert success is False
        assert new_path is None

    def test_returns_false_when_new_name_exists(self, tmp_path):
        """Test that False is returned when new name already exists."""
        old_file = tmp_path / "old_name.txt"
        old_file.write_text("content")
        existing_file = tmp_path / "new_name.txt"
        existing_file.write_text("existing")

        success, new_path = perform_rename(old_file, "new_name.txt")

        assert success is False
        assert new_path is None

    def test_handles_rename_errors(self, tmp_path):
        """Test that rename errors are handled."""
        old_file = tmp_path / "old_name.txt"
        old_file.write_text("content")

        with patch("pathlib.Path.rename") as mock_rename:
            mock_rename.side_effect = OSError("Permission denied")

            success, new_path = perform_rename(old_file, "new_name.txt")

            assert success is False
            assert new_path is None


class TestRenameFileInteractive:
    """Tests for rename_file_interactive function."""

    def test_prompts_for_new_name(self, tmp_path):
        """Test that user is prompted for new name."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("content")

        with (
            patch("transcriptx.cli.file_rename_handler.questionary") as mock_q,
            patch("transcriptx.cli.file_rename_handler.perform_rename") as mock_rename,
        ):

            mock_q.text.return_value.ask.return_value = "new_name.txt"
            mock_rename.return_value = (True, tmp_path / "new_name.txt")

            result = rename_file_interactive(file_path)

            assert result == "new_name.txt"
            mock_q.text.assert_called_once()

    def test_returns_none_when_cancelled(self, tmp_path):
        """Test that None is returned when user cancels."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("content")

        with patch("transcriptx.cli.file_rename_handler.questionary") as mock_q:
            mock_q.text.return_value.ask.return_value = ""

            result = rename_file_interactive(file_path)

            assert result is None

    def test_validates_filename_before_rename(self, tmp_path):
        """Test that filename is validated before rename."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("content")

        with (
            patch("transcriptx.cli.file_rename_handler.questionary") as mock_q,
            patch(
                "transcriptx.cli.file_rename_handler.validate_filename"
            ) as mock_validate,
        ):

            mock_q.text.return_value.ask.return_value = "invalid/name.txt"
            mock_validate.return_value = (False, "Invalid characters")

            result = rename_file_interactive(file_path)

            # Should not rename invalid filename
            assert result is None or result != "invalid/name.txt"
            mock_validate.assert_called()

    def test_handles_keyboard_interrupt(self, tmp_path):
        """Test that KeyboardInterrupt is handled."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("content")

        with patch("transcriptx.cli.file_rename_handler.questionary") as mock_q:
            mock_q.text.return_value.ask.side_effect = KeyboardInterrupt()

            result = rename_file_interactive(file_path)

            assert result is None
