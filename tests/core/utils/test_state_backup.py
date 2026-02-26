"""
Tests for state backup and recovery utilities.

This module tests backup creation, rotation, recovery, and validation.
"""

import json
from unittest.mock import patch


from transcriptx.core.utils.state_backup import (
    create_backup,
    rotate_backups,
    list_backups,
    restore_from_backup,
    verify_backup,
)


class TestCreateBackup:
    """Tests for create_backup function."""

    def test_creates_backup_file(self, tmp_path, monkeypatch):
        """Test that backup file is created."""
        # Set up test state file
        state_file = tmp_path / "processing_state.json"
        state_data = {"processed_files": {"test": {"status": "completed"}}}
        state_file.write_text(json.dumps(state_data))

        # Set up backup directory
        backup_dir = tmp_path / "backups" / "processing_state"

        with (
            patch(
                "transcriptx.core.utils.state_backup.PROCESSING_STATE_FILE", state_file
            ),
            patch("transcriptx.core.utils.state_backup.BACKUP_DIR", backup_dir),
        ):

            backup_path = create_backup()

            assert backup_path is not None
            assert backup_path.exists()
            assert backup_path.name.startswith("processing_state_")
            assert backup_path.name.endswith(".json.backup")

            # Verify backup content
            with open(backup_path) as f:
                backup_data = json.load(f)
            assert backup_data == state_data

    def test_returns_none_when_state_file_not_exists(self, tmp_path, monkeypatch):
        """Test that None is returned when state file doesn't exist."""
        state_file = tmp_path / "nonexistent.json"
        backup_dir = tmp_path / "backups" / "processing_state"

        with (
            patch(
                "transcriptx.core.utils.state_backup.PROCESSING_STATE_FILE", state_file
            ),
            patch("transcriptx.core.utils.state_backup.BACKUP_DIR", backup_dir),
        ):

            backup_path = create_backup()

            assert backup_path is None

    def test_creates_backup_directory_if_needed(self, tmp_path, monkeypatch):
        """Test that backup directory is created if it doesn't exist."""
        state_file = tmp_path / "processing_state.json"
        state_data = {"processed_files": {}}
        state_file.write_text(json.dumps(state_data))

        backup_dir = tmp_path / "backups" / "processing_state"

        with (
            patch(
                "transcriptx.core.utils.state_backup.PROCESSING_STATE_FILE", state_file
            ),
            patch("transcriptx.core.utils.state_backup.BACKUP_DIR", backup_dir),
        ):

            backup_path = create_backup()

            assert backup_dir.exists()
            assert backup_path is not None

    def test_uses_custom_state_file(self, tmp_path, monkeypatch):
        """Test that custom state file path can be provided."""
        custom_state_file = tmp_path / "custom_state.json"
        state_data = {"processed_files": {"test": {}}}
        custom_state_file.write_text(json.dumps(state_data))

        backup_dir = tmp_path / "backups" / "processing_state"

        with patch("transcriptx.core.utils.state_backup.BACKUP_DIR", backup_dir):
            backup_path = create_backup(custom_state_file)

            assert backup_path is not None
            assert backup_path.exists()

    def test_calls_rotate_backups(self, tmp_path, monkeypatch):
        """Test that rotate_backups is called after creating backup."""
        state_file = tmp_path / "processing_state.json"
        state_data = {"processed_files": {}}
        state_file.write_text(json.dumps(state_data))

        backup_dir = tmp_path / "backups" / "processing_state"

        with (
            patch(
                "transcriptx.core.utils.state_backup.PROCESSING_STATE_FILE", state_file
            ),
            patch("transcriptx.core.utils.state_backup.BACKUP_DIR", backup_dir),
            patch("transcriptx.core.utils.state_backup.rotate_backups") as mock_rotate,
        ):

            create_backup()

            mock_rotate.assert_called_once()

    def test_handles_backup_creation_errors(self, tmp_path, monkeypatch):
        """Test that errors during backup creation are handled."""
        state_file = tmp_path / "processing_state.json"
        state_data = {"processed_files": {}}
        state_file.write_text(json.dumps(state_data))

        backup_dir = tmp_path / "backups" / "processing_state"

        with (
            patch(
                "transcriptx.core.utils.state_backup.PROCESSING_STATE_FILE", state_file
            ),
            patch("transcriptx.core.utils.state_backup.BACKUP_DIR", backup_dir),
            patch("shutil.copy2") as mock_copy,
        ):

            mock_copy.side_effect = OSError("Permission denied")

            backup_path = create_backup()

            assert backup_path is None


class TestRotateBackups:
    """Tests for rotate_backups function."""

    def test_keeps_only_max_backups(self, tmp_path, monkeypatch):
        """Test that only MAX_BACKUPS are kept."""
        backup_dir = tmp_path / "backups" / "processing_state"
        backup_dir.mkdir(parents=True)

        # Create more backups than MAX_BACKUPS
        max_backups = 10
        for i in range(15):
            backup_file = (
                backup_dir / f"processing_state_20250101_{i:02d}0000.json.backup"
            )
            backup_file.write_text(json.dumps({"test": i}))
            # Set modification time to make them sortable
            import time

            backup_file.touch()
            time.sleep(0.01)  # Small delay to ensure different mtimes

        with (
            patch("transcriptx.core.utils.state_backup.BACKUP_DIR", backup_dir),
            patch("transcriptx.core.utils.state_backup.MAX_BACKUPS", max_backups),
        ):

            rotate_backups()

            # Should only have MAX_BACKUPS files
            backups = list(backup_dir.glob("processing_state_*.json.backup"))
            assert len(backups) == max_backups

    def test_removes_oldest_backups(self, tmp_path, monkeypatch):
        """Test that oldest backups are removed."""
        backup_dir = tmp_path / "backups" / "processing_state"
        backup_dir.mkdir(parents=True)

        # Create backups with different modification times
        import time

        for i in range(5):
            backup_file = backup_dir / f"processing_state_old_{i}.json.backup"
            backup_file.write_text(json.dumps({"test": i}))
            backup_file.touch()
            time.sleep(0.01)

        for i in range(5):
            backup_file = backup_dir / f"processing_state_new_{i}.json.backup"
            backup_file.write_text(json.dumps({"test": i + 10}))
            backup_file.touch()
            time.sleep(0.01)

        with (
            patch("transcriptx.core.utils.state_backup.BACKUP_DIR", backup_dir),
            patch("transcriptx.core.utils.state_backup.MAX_BACKUPS", 5),
        ):

            rotate_backups()

            # Should keep newest 5
            backups = list(backup_dir.glob("processing_state_*.json.backup"))
            assert len(backups) == 5
            # New backups should be kept
            new_backups = [b for b in backups if "new" in b.name]
            assert len(new_backups) == 5

    def test_handles_nonexistent_backup_dir(self, tmp_path, monkeypatch):
        """Test that function handles nonexistent backup directory."""
        backup_dir = tmp_path / "nonexistent" / "backups"

        with patch("transcriptx.core.utils.state_backup.BACKUP_DIR", backup_dir):
            # Should not raise error
            rotate_backups()

    def test_handles_removal_errors(self, tmp_path, monkeypatch):
        """Test that errors during backup removal are handled."""
        backup_dir = tmp_path / "backups" / "processing_state"
        backup_dir.mkdir(parents=True)

        # Create backup file
        backup_file = backup_dir / "processing_state_test.json.backup"
        backup_file.write_text(json.dumps({"test": "data"}))

        with (
            patch("transcriptx.core.utils.state_backup.BACKUP_DIR", backup_dir),
            patch("transcriptx.core.utils.state_backup.MAX_BACKUPS", 0),
            patch("pathlib.Path.unlink") as mock_unlink,
        ):

            mock_unlink.side_effect = OSError("Permission denied")

            # Should not raise error
            rotate_backups()


class TestListBackups:
    """Tests for list_backups function."""

    def test_returns_empty_list_when_no_backups(self, tmp_path, monkeypatch):
        """Test that empty list is returned when no backups exist."""
        backup_dir = tmp_path / "backups" / "processing_state"

        with patch("transcriptx.core.utils.state_backup.BACKUP_DIR", backup_dir):
            backups = list_backups()

            assert backups == []

    def test_returns_backup_information(self, tmp_path, monkeypatch):
        """Test that backup information is returned."""
        backup_dir = tmp_path / "backups" / "processing_state"
        backup_dir.mkdir(parents=True)

        backup_file = backup_dir / "processing_state_20250101_120000.json.backup"
        backup_data = {"processed_files": {"test": {}}}
        backup_file.write_text(json.dumps(backup_data))

        with patch("transcriptx.core.utils.state_backup.BACKUP_DIR", backup_dir):
            backups = list_backups()

            assert len(backups) == 1
            assert backups[0]["path"] == str(backup_file)
            assert backups[0]["name"] == backup_file.name
            assert "size" in backups[0]
            assert "created" in backups[0]

    def test_sorts_backups_by_modification_time(self, tmp_path, monkeypatch):
        """Test that backups are sorted by modification time (newest first)."""
        backup_dir = tmp_path / "backups" / "processing_state"
        backup_dir.mkdir(parents=True)

        import time

        # Create backups with different modification times
        for i in range(3):
            backup_file = backup_dir / f"processing_state_{i}.json.backup"
            backup_file.write_text(json.dumps({"test": i}))
            backup_file.touch()
            time.sleep(0.01)

        with patch("transcriptx.core.utils.state_backup.BACKUP_DIR", backup_dir):
            backups = list_backups()

            # Should be sorted newest first
            assert len(backups) == 3
            # Check that modification times are descending
            for i in range(len(backups) - 1):
                assert backups[i]["created"] >= backups[i + 1]["created"]


class TestRestoreFromBackup:
    """Tests for restore_from_backup function."""

    def test_restores_state_from_backup(self, tmp_path, monkeypatch):
        """Test that state is restored from backup."""
        state_file = tmp_path / "processing_state.json"
        state_file.write_text(json.dumps({"processed_files": {"old": {}}}))

        backup_file = tmp_path / "backup.json.backup"
        backup_data = {"processed_files": {"restored": {"status": "completed"}}}
        backup_file.write_text(json.dumps(backup_data))

        with patch(
            "transcriptx.core.utils.state_backup.PROCESSING_STATE_FILE", state_file
        ):
            result = restore_from_backup(backup_file)

            assert result is True
            with open(state_file) as f:
                restored_data = json.load(f)
            assert restored_data == backup_data

    def test_creates_backup_before_restore(self, tmp_path, monkeypatch):
        """Test that backup is created before restore."""
        state_file = tmp_path / "processing_state.json"
        state_data = {"processed_files": {"old": {}}}
        state_file.write_text(json.dumps(state_data))

        backup_file = tmp_path / "backup.json.backup"
        backup_data = {"processed_files": {"restored": {}}}
        backup_file.write_text(json.dumps(backup_data))

        backup_dir = tmp_path / "backups" / "processing_state"

        with (
            patch(
                "transcriptx.core.utils.state_backup.PROCESSING_STATE_FILE", state_file
            ),
            patch("transcriptx.core.utils.state_backup.BACKUP_DIR", backup_dir),
            patch("transcriptx.core.utils.state_backup.create_backup") as mock_backup,
        ):

            restore_from_backup(backup_file)

            mock_backup.assert_called_once_with(state_file)

    def test_returns_false_when_backup_not_exists(self, tmp_path, monkeypatch):
        """Test that False is returned when backup file doesn't exist."""
        backup_file = tmp_path / "nonexistent.json.backup"

        result = restore_from_backup(backup_file)

        assert result is False

    def test_returns_false_when_backup_invalid_json(self, tmp_path, monkeypatch):
        """Test that False is returned when backup is invalid JSON."""
        backup_file = tmp_path / "invalid.json.backup"
        backup_file.write_text("invalid json content")

        result = restore_from_backup(backup_file)

        assert result is False

    def test_uses_custom_state_file(self, tmp_path, monkeypatch):
        """Test that custom state file path can be provided."""
        custom_state_file = tmp_path / "custom_state.json"
        custom_state_file.write_text(json.dumps({"old": {}}))

        backup_file = tmp_path / "backup.json.backup"
        backup_data = {"restored": True}
        backup_file.write_text(json.dumps(backup_data))

        result = restore_from_backup(backup_file, custom_state_file)

        assert result is True
        with open(custom_state_file) as f:
            restored_data = json.load(f)
        assert restored_data == backup_data

    def test_handles_restore_errors(self, tmp_path, monkeypatch):
        """Test that errors during restore are handled."""
        state_file = tmp_path / "processing_state.json"
        state_file.write_text(json.dumps({"old": {}}))

        backup_file = tmp_path / "backup.json.backup"
        backup_file.write_text(json.dumps({"restored": True}))

        with (
            patch(
                "transcriptx.core.utils.state_backup.PROCESSING_STATE_FILE", state_file
            ),
            patch("shutil.copy2") as mock_copy,
        ):

            mock_copy.side_effect = OSError("Permission denied")

            result = restore_from_backup(backup_file)

            assert result is False


class TestVerifyBackup:
    """Tests for verify_backup function."""

    def test_returns_true_for_valid_backup(self, tmp_path):
        """Test that True is returned for valid backup."""
        backup_file = tmp_path / "backup.json.backup"
        backup_data = {"processed_files": {"test": {"status": "completed"}}}
        backup_file.write_text(json.dumps(backup_data))

        result = verify_backup(backup_file)

        assert result is True

    def test_returns_false_when_backup_not_exists(self, tmp_path):
        """Test that False is returned when backup doesn't exist."""
        backup_file = tmp_path / "nonexistent.json.backup"

        result = verify_backup(backup_file)

        assert result is False

    def test_returns_false_for_invalid_json(self, tmp_path):
        """Test that False is returned for invalid JSON."""
        backup_file = tmp_path / "invalid.json.backup"
        backup_file.write_text("invalid json content")

        result = verify_backup(backup_file)

        assert result is False

    def test_returns_false_when_not_dict(self, tmp_path):
        """Test that False is returned when backup is not a dict."""
        backup_file = tmp_path / "backup.json.backup"
        backup_file.write_text(json.dumps(["not", "a", "dict"]))

        result = verify_backup(backup_file)

        assert result is False

    def test_returns_false_when_missing_processed_files(self, tmp_path):
        """Test that False is returned when 'processed_files' key is missing."""
        backup_file = tmp_path / "backup.json.backup"
        backup_file.write_text(json.dumps({"other": "data"}))

        result = verify_backup(backup_file)

        assert result is False
