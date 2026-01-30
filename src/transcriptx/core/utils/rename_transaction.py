"""
Atomic rename operations with rollback support.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import DATA_DIR
from transcriptx.core.utils.state_backup import create_backup
from transcriptx.core.utils.file_lock import FileLock

logger = get_logger()


class RenameTransaction:
    """
    Transaction-like rename operation with rollback capability.
    """

    def __init__(self, dry_run: bool = False):
        """
        Initialize rename transaction.

        Args:
            dry_run: If True, don't actually perform renames
        """
        self.dry_run = dry_run
        self.operations: List[Dict[str, Any]] = []
        self.executed: List[Dict[str, Any]] = []
        self.backup_path: Optional[Path] = None

    def add_rename(self, source: Path, dest: Path, description: str = "") -> None:
        """
        Add a rename operation to the transaction.

        Args:
            source: Source file path
            dest: Destination file path
            description: Description of the operation
        """
        self.operations.append(
            {
                "type": "rename",
                "source": source,
                "dest": dest,
                "description": description,
                "executed": False,
            }
        )

    def add_state_update(self, update_func, *args, **kwargs) -> None:
        """
        Add a state update operation to the transaction.

        Args:
            update_func: Function to call for state update
            *args: Arguments for update function
            **kwargs: Keyword arguments for update function
        """
        self.operations.append(
            {
                "type": "state_update",
                "func": update_func,
                "args": args,
                "kwargs": kwargs,
                "executed": False,
            }
        )

    def execute(self) -> bool:
        """
        Execute all operations in the transaction.

        Returns:
            True if successful, False otherwise
        """
        if self.dry_run:
            logger.info("DRY RUN: Would execute the following operations:")
            for op in self.operations:
                logger.info(f"  - {op.get('description', op['type'])}")
            return True

        # Create backup before starting
        state_file = Path(DATA_DIR) / "processing_state.json"
        if state_file.exists():
            self.backup_path = create_backup(state_file)

        # Acquire lock
        with FileLock(state_file, timeout=30) as lock:
            if not lock.acquired:
                logger.error("Could not acquire lock for rename transaction")
                return False

            try:
                # Execute all operations
                for op in self.operations:
                    if op["type"] == "rename":
                        result = self._execute_rename(op)
                    elif op["type"] == "state_update":
                        result = self._execute_state_update(op)
                    else:
                        logger.error(f"Unknown operation type: {op['type']}")
                        result = False

                    if not result:
                        # Rollback on failure
                        self.rollback()
                        return False

                    op["executed"] = True
                    self.executed.append(op)

                return True

            except Exception as e:
                logger.error(f"Error during rename transaction: {e}")
                self.rollback()
                return False

    def _execute_rename(self, op: Dict[str, Any]) -> bool:
        """Execute a rename operation."""
        source = op["source"]
        dest = op["dest"]

        if not source.exists():
            logger.error(f"Source file does not exist: {source}")
            return False

        if dest.exists():
            logger.error(f"Destination file already exists: {dest}")
            return False

        try:
            # Ensure destination directory exists
            dest.parent.mkdir(parents=True, exist_ok=True)

            # Perform rename
            source.rename(dest)
            logger.debug(f"Renamed: {source} -> {dest}")
            return True
        except Exception as e:
            logger.error(f"Failed to rename {source} to {dest}: {e}")
            return False

    def _execute_state_update(self, op: Dict[str, Any]) -> bool:
        """Execute a state update operation."""
        try:
            op["func"](*op["args"], **op["kwargs"])
            return True
        except Exception as e:
            logger.error(f"Failed to execute state update: {e}")
            return False

    def rollback(self) -> None:
        """Rollback all executed operations."""
        logger.warning("Rolling back rename transaction")

        # Rollback in reverse order
        for op in reversed(self.executed):
            if op["type"] == "rename":
                source = op["source"]
                dest = op["dest"]

                if dest.exists():
                    try:
                        dest.rename(source)
                        logger.debug(f"Rolled back rename: {dest} -> {source}")
                    except Exception as e:
                        logger.error(f"Failed to rollback rename: {e}")

        # Restore state from backup if available
        if self.backup_path:
            from transcriptx.core.utils.state_backup import restore_from_backup

            restore_from_backup(self.backup_path)
