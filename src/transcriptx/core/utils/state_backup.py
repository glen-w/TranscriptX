"""
State file backup and recovery utilities.

This module provides automatic backup creation, rotation, and recovery
for the processing state file.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import DATA_DIR

logger = get_logger()

PROCESSING_STATE_FILE = Path(DATA_DIR) / "processing_state.json"
BACKUP_DIR = Path(DATA_DIR) / "backups" / "processing_state"
MAX_BACKUPS = 5  # Keep last 5 backups


def create_backup(state_file: Optional[Path] = None) -> Optional[Path]:
    """
    Create a backup of the processing state file.

    Args:
        state_file: Path to state file (defaults to standard location)

    Returns:
        Path to backup file if successful, None otherwise
    """
    if state_file is None:
        state_file = PROCESSING_STATE_FILE

    if not state_file.exists():
        logger.warning(f"State file does not exist: {state_file}")
        return None

    # Ensure backup directory exists
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # Create backup filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"processing_state_{timestamp}.json.backup"
    backup_path = BACKUP_DIR / backup_filename

    try:
        # Copy state file to backup
        shutil.copy2(state_file, backup_path)
        logger.info(f"Created backup: {backup_path}")

        # Rotate old backups
        rotate_backups()

        return backup_path
    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        return None


def rotate_backups() -> None:
    """Remove old backups, keeping only the last MAX_BACKUPS."""
    if not BACKUP_DIR.exists():
        return

    # Get all backup files sorted by modification time
    backups = sorted(
        BACKUP_DIR.glob("processing_state_*.json.backup"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    # Remove backups beyond MAX_BACKUPS
    for backup in backups[MAX_BACKUPS:]:
        try:
            backup.unlink()
            logger.debug(f"Removed old backup: {backup}")
        except Exception as e:
            logger.warning(f"Failed to remove old backup {backup}: {e}")


def list_backups() -> List[Dict[str, Any]]:
    """
    List all available backups.

    Returns:
        List of backup information dictionaries
    """
    if not BACKUP_DIR.exists():
        return []

    backups = []
    for backup_path in sorted(
        BACKUP_DIR.glob("processing_state_*.json.backup"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        stat = backup_path.stat()
        backups.append(
            {
                "path": str(backup_path),
                "size": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "name": backup_path.name,
            }
        )

    return backups


def restore_from_backup(backup_path: Path, state_file: Optional[Path] = None) -> bool:
    """
    Restore processing state from a backup file.

    Args:
        backup_path: Path to backup file
        state_file: Path to state file to restore (defaults to standard location)

    Returns:
        True if successful, False otherwise
    """
    if state_file is None:
        state_file = PROCESSING_STATE_FILE

    if not backup_path.exists():
        logger.error(f"Backup file does not exist: {backup_path}")
        return False

    # Validate backup file
    try:
        with open(backup_path, "r") as f:
            json.load(f)  # Validate JSON
    except Exception as e:
        logger.error(f"Backup file is not valid JSON: {e}")
        return False

    # Create backup of current state before restore
    if state_file.exists():
        create_backup(state_file)

    try:
        # Restore from backup
        shutil.copy2(backup_path, state_file)
        logger.info(f"Restored state from backup: {backup_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to restore from backup: {e}")
        return False


def verify_backup(backup_path: Path) -> bool:
    """
    Verify that a backup file is valid.

    Args:
        backup_path: Path to backup file

    Returns:
        True if valid, False otherwise
    """
    if not backup_path.exists():
        return False

    try:
        with open(backup_path, "r") as f:
            state = json.load(f)

        # Basic validation
        if not isinstance(state, dict):
            return False

        if "processed_files" not in state:
            return False

        return True
    except Exception:
        return False
