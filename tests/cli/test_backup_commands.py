"""
Tests for backup CLI commands.

This module tests backup command execution, listing, and restoration.
"""

import json
from unittest.mock import patch


from transcriptx.cli.backup_commands import (
    list_state_backups,
    restore_state_backup,
    create_manual_backup,
)


class TestListStateBackups:
    """Tests for list_state_backups function."""

    def test_displays_backups_table(self, tmp_path, monkeypatch):
        """Test that backups are displayed in a table."""
        backup_dir = tmp_path / "backups" / "processing_state"
        backup_dir.mkdir(parents=True)

        backup_file = backup_dir / "processing_state_20250101_120000.json.backup"
        backup_data = {"processed_files": {"test": {}}}
        backup_file.write_text(json.dumps(backup_data))

        with (
            patch("transcriptx.cli.backup_commands.list_backups") as mock_list,
            patch("transcriptx.cli.backup_commands.console") as mock_console,
            patch("transcriptx.cli.backup_commands.verify_backup") as mock_verify,
        ):

            mock_list.return_value = [
                {
                    "name": backup_file.name,
                    "path": str(backup_file),
                    "size": 1024,
                    "created": "2025-01-01T12:00:00",
                }
            ]
            mock_verify.return_value = True

            list_state_backups()

            # Should print table
            assert mock_console.print.called

    def test_displays_message_when_no_backups(self):
        """Test that message is displayed when no backups exist."""
        with (
            patch("transcriptx.cli.backup_commands.list_backups") as mock_list,
            patch("transcriptx.cli.backup_commands.console") as mock_console,
        ):

            mock_list.return_value = []

            list_state_backups()

            # Should print "No backups found"
            call_args = str(mock_console.print.call_args)
            assert "No backups" in call_args or "yellow" in call_args

    def test_shows_validity_status(self, tmp_path):
        """Test that backup validity is shown."""
        backup_dir = tmp_path / "backups" / "processing_state"
        backup_dir.mkdir(parents=True)

        backup_file = backup_dir / "processing_state_test.json.backup"
        backup_file.write_text(json.dumps({"processed_files": {}}))

        with (
            patch("transcriptx.cli.backup_commands.list_backups") as mock_list,
            patch("transcriptx.cli.backup_commands.console") as mock_console,
            patch("transcriptx.cli.backup_commands.verify_backup") as mock_verify,
        ):

            mock_list.return_value = [
                {
                    "name": backup_file.name,
                    "path": str(backup_file),
                    "size": 1024,
                    "created": "2025-01-01T12:00:00",
                }
            ]
            mock_verify.return_value = True

            list_state_backups()

            # Should verify backup
            mock_verify.assert_called()


class TestRestoreStateBackup:
    """Tests for restore_state_backup function."""

    def test_restores_selected_backup(self, tmp_path):
        """Test that selected backup is restored."""
        backup_file = tmp_path / "backup.json.backup"
        backup_file.write_text(json.dumps({"processed_files": {}}))

        with (
            patch("transcriptx.cli.backup_commands.list_backups") as mock_list,
            patch("transcriptx.cli.backup_commands.questionary") as mock_q,
            patch(
                "transcriptx.cli.backup_commands.restore_from_backup"
            ) as mock_restore,
            patch("transcriptx.cli.backup_commands.console") as mock_console,
        ):

            mock_list.return_value = [
                {
                    "name": backup_file.name,
                    "path": str(backup_file),
                    "created": "2025-01-01T12:00:00",
                }
            ]
            mock_q.select.return_value.ask.return_value = (
                f"{backup_file.name} (2025-01-01T12:00:00)"
            )
            mock_q.confirm.return_value.ask.return_value = True
            mock_restore.return_value = True

            restore_state_backup()

            # Should restore backup
            mock_restore.assert_called()
            mock_console.print.assert_called()

    def test_shows_message_when_no_backups(self):
        """Test that message is shown when no backups available."""
        with (
            patch("transcriptx.cli.backup_commands.list_backups") as mock_list,
            patch("transcriptx.cli.backup_commands.console") as mock_console,
        ):

            mock_list.return_value = []

            restore_state_backup()

            # Should print message
            call_args = str(mock_console.print.call_args)
            assert "No backups" in call_args or "yellow" in call_args

    def test_cancels_when_user_cancels_selection(self):
        """Test that restore is cancelled when user cancels selection."""
        with (
            patch("transcriptx.cli.backup_commands.list_backups") as mock_list,
            patch("transcriptx.cli.backup_commands.questionary") as mock_q,
            patch(
                "transcriptx.cli.backup_commands.restore_from_backup"
            ) as mock_restore,
        ):

            mock_list.return_value = [
                {
                    "name": "backup.json.backup",
                    "path": "/path/to/backup",
                    "created": "2025-01-01",
                }
            ]
            mock_q.select.return_value.ask.return_value = None

            restore_state_backup()

            # Should not restore
            mock_restore.assert_not_called()

    def test_cancels_when_user_cancels_confirmation(self, tmp_path):
        """Test that restore is cancelled when user cancels confirmation."""
        backup_file = tmp_path / "backup.json.backup"

        with (
            patch("transcriptx.cli.backup_commands.list_backups") as mock_list,
            patch("transcriptx.cli.backup_commands.questionary") as mock_q,
            patch(
                "transcriptx.cli.backup_commands.restore_from_backup"
            ) as mock_restore,
        ):

            mock_list.return_value = [
                {
                    "name": backup_file.name,
                    "path": str(backup_file),
                    "created": "2025-01-01",
                }
            ]
            mock_q.select.return_value.ask.return_value = (
                f"{backup_file.name} (2025-01-01)"
            )
            mock_q.confirm.return_value.ask.return_value = False

            restore_state_backup()

            # Should not restore
            mock_restore.assert_not_called()

    def test_shows_error_on_restore_failure(self, tmp_path):
        """Test that error is shown when restore fails."""
        backup_file = tmp_path / "backup.json.backup"

        with (
            patch("transcriptx.cli.backup_commands.list_backups") as mock_list,
            patch("transcriptx.cli.backup_commands.questionary") as mock_q,
            patch(
                "transcriptx.cli.backup_commands.restore_from_backup"
            ) as mock_restore,
            patch("transcriptx.cli.backup_commands.console") as mock_console,
        ):

            mock_list.return_value = [
                {
                    "name": backup_file.name,
                    "path": str(backup_file),
                    "created": "2025-01-01",
                }
            ]
            mock_q.select.return_value.ask.return_value = (
                f"{backup_file.name} (2025-01-01)"
            )
            mock_q.confirm.return_value.ask.return_value = True
            mock_restore.return_value = False

            restore_state_backup()

            # Should show error
            call_args = str(mock_console.print.call_args)
            assert "Failed" in call_args or "red" in call_args


class TestCreateManualBackup:
    """Tests for create_manual_backup function."""

    def test_creates_backup_successfully(self, tmp_path):
        """Test that backup is created successfully."""
        backup_file = tmp_path / "backup.json.backup"

        with (
            patch("transcriptx.cli.backup_commands.create_backup") as mock_create,
            patch("transcriptx.cli.backup_commands.console") as mock_console,
        ):

            mock_create.return_value = backup_file

            create_manual_backup()

            # Should create backup and show success
            mock_create.assert_called_once()
            call_args = str(mock_console.print.call_args)
            assert "created" in call_args.lower() or "green" in call_args

    def test_shows_error_on_failure(self):
        """Test that error is shown when backup creation fails."""
        with (
            patch("transcriptx.cli.backup_commands.create_backup") as mock_create,
            patch("transcriptx.cli.backup_commands.console") as mock_console,
        ):

            mock_create.return_value = None

            create_manual_backup()

            # Should show error
            call_args = str(mock_console.print.call_args)
            assert "Failed" in call_args or "red" in call_args
