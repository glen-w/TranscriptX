"""
Rollback-capable rename operations (not fully atomic across all storage).

``rollback()`` is only valid for failures **during** ``execute()``. Post-commit
finalize failures must not invoke ``rollback()``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from transcriptx.core.utils.file_lock import FileLock
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.rename.names import (
    paths_are_case_only_rename,
    unique_temp_name,
)
from transcriptx.core.utils.state_backup import create_backup

logger = get_logger()


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    from transcriptx.core.utils.rename.io_atomic import write_json_atomic

    write_json_atomic(path, payload)


def _write_bytes_atomic(path: Path, data: bytes) -> None:
    from transcriptx.core.utils.rename.io_atomic import write_bytes_atomic

    write_bytes_atomic(path, data)


@dataclass
class RollbackResult:
    ok: bool
    errors: list[str] = field(default_factory=list)


@dataclass
class TransactionResult:
    ok: bool
    failure_code: str = ""
    failure_message: str = ""
    rollback: RollbackResult | None = None

    @property
    def rollback_complete(self) -> bool:
        return self.rollback is not None and self.rollback.ok


class RenameTransaction:
    """Rollback-capable transaction for file renames and staged JSON writes."""

    def __init__(
        self,
        *,
        processing_state_file: Path | None = None,
        dry_run: bool = False,
    ):
        self.dry_run = dry_run
        self.processing_state_file = (
            Path(processing_state_file) if processing_state_file is not None else None
        )
        self.operations: List[Dict[str, Any]] = []
        self.executed: List[Dict[str, Any]] = []
        self.backup_path: Optional[Path] = None
        self._created_parents: list[Path] = []
        self._current_op: Dict[str, Any] | None = None

    def add_rename(self, source: Path, dest: Path, description: str = "") -> None:
        self.operations.append(
            {
                "type": "rename",
                "source": Path(source),
                "dest": Path(dest),
                "description": description,
                "executed": False,
                "temp": None,
            }
        )

    def add_state_update(self, update_func, *args, **kwargs) -> None:
        self.operations.append(
            {
                "type": "state_update",
                "func": update_func,
                "args": args,
                "kwargs": kwargs,
                "description": "processing_state_update",
                "executed": False,
            }
        )

    def add_json_write(
        self, path: Path, payload: dict[str, Any], description: str = ""
    ) -> None:
        self.operations.append(
            {
                "type": "json_write",
                "path": Path(path),
                "payload": payload,
                "description": description,
                "executed": False,
                "existed_before": False,
                "before_bytes": None,
            }
        )

    def execute(self) -> TransactionResult:
        if self.dry_run:
            logger.info("DRY RUN: Would execute the following operations:")
            for op in self.operations:
                logger.info("  - %s", op.get("description", op["type"]))
            return TransactionResult(ok=True)

        state_file = self.processing_state_file
        if state_file is None:
            msg = "RenameTransaction requires an explicit processing_state_file"
            logger.error("%s", msg)
            return TransactionResult(
                ok=False,
                failure_code="missing_state_file",
                failure_message=msg,
            )

        with FileLock(state_file, timeout=30) as lock:
            if not lock.acquired:
                msg = "Could not acquire lock for rename transaction"
                logger.error("%s", msg)
                return TransactionResult(
                    ok=False,
                    failure_code="lock_failed",
                    failure_message=msg,
                )

            if state_file.exists():
                self.backup_path = create_backup(state_file)

            try:
                for op in self.operations:
                    self._current_op = op
                    if op not in self.executed:
                        self.executed.append(op)

                    if op["type"] == "rename":
                        result, code, message = self._execute_rename(op)
                    elif op["type"] == "state_update":
                        result, code, message = self._execute_state_update(op)
                    elif op["type"] == "json_write":
                        result, code, message = self._execute_json_write(op)
                    else:
                        result, code, message = (
                            False,
                            "unknown_operation",
                            f"Unknown operation type: {op['type']}",
                        )
                        logger.error("%s", message)

                    if not result:
                        rollback = self.rollback()
                        self._current_op = None
                        return TransactionResult(
                            ok=False,
                            failure_code=code,
                            failure_message=message,
                            rollback=rollback,
                        )

                    op["executed"] = True
                    self._current_op = None

                return TransactionResult(ok=True)
            except Exception as e:
                logger.error("Error during rename transaction: %s", e)
                rollback = self.rollback()
                self._current_op = None
                return TransactionResult(
                    ok=False,
                    failure_code="transaction_exception",
                    failure_message=str(e),
                    rollback=rollback,
                )

    def _note_created_parent(self, dest: Path) -> None:
        parent = dest.parent
        created: list[Path] = []
        cursor = parent
        while not cursor.exists():
            created.append(cursor)
            if cursor.parent == cursor:
                break
            cursor = cursor.parent
        for path in reversed(created):
            path.mkdir(parents=False, exist_ok=True)
            self._created_parents.append(path)

    def _execute_rename(self, op: Dict[str, Any]) -> tuple[bool, str, str]:
        source = op["source"]
        dest = op["dest"]

        if not source.exists():
            msg = f"Source file does not exist: {source}"
            logger.error("%s", msg)
            return False, "source_missing", msg

        try:
            if not dest.parent.exists():
                self._note_created_parent(dest)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)

            if paths_are_case_only_rename(source, dest):
                tmp = unique_temp_name(source.parent, dest.name)
                source.rename(tmp)
                op["temp"] = tmp
                try:
                    tmp.rename(dest)
                except Exception as e:
                    msg = f"Failed case-only rename {source} to {dest}: {e}"
                    logger.error("%s", msg)
                    return False, "case_only_second_move_failed", msg
                op["temp"] = None
            else:
                if dest.exists():
                    msg = f"Destination file already exists: {dest}"
                    logger.error("%s", msg)
                    return False, "destination_exists", msg
                source.rename(dest)
            logger.debug("Renamed: %s -> %s", source, dest)
            return True, "", ""
        except Exception as e:
            msg = f"Failed to rename {source} to {dest}: {e}"
            logger.error("%s", msg)
            return False, "rename_failed", msg

    def _execute_state_update(self, op: Dict[str, Any]) -> tuple[bool, str, str]:
        try:
            op["func"](*op["args"], **op["kwargs"])
            return True, "", ""
        except Exception as e:
            msg = f"Failed to execute state update: {e}"
            logger.error("%s", msg)
            return False, "state_update_failed", msg

    def _execute_json_write(self, op: Dict[str, Any]) -> tuple[bool, str, str]:
        path: Path = op["path"]
        try:
            existed = path.exists()
            op["existed_before"] = existed
            op["before_bytes"] = path.read_bytes() if existed else None
            if not path.parent.exists():
                self._note_created_parent(path)
            _write_json_atomic(path, op["payload"])
            return True, "", ""
        except Exception as e:
            msg = f"Failed JSON write {path}: {e}"
            logger.error("%s", msg)
            return False, "json_write_failed", msg

    def rollback(self) -> RollbackResult:
        logger.warning("Rolling back rename transaction")
        errors: list[str] = []

        for op in reversed(self.executed):
            if op["type"] == "rename":
                source = op["source"]
                dest = op["dest"]
                temp = op.get("temp")
                try:
                    if temp is not None and Path(temp).exists():
                        Path(temp).rename(source)
                    elif dest.exists() and (
                        op.get("executed") or temp is not None or not source.exists()
                    ):
                        if paths_are_case_only_rename(dest, source):
                            tmp = unique_temp_name(dest.parent, source.name)
                            dest.rename(tmp)
                            tmp.rename(source)
                        else:
                            dest.rename(source)
                        logger.debug("Rolled back rename: %s -> %s", dest, source)
                except Exception as e:
                    err = f"Failed to rollback rename {dest} -> {source}: {e}"
                    logger.error("%s", err)
                    errors.append(err)
            elif op["type"] == "json_write":
                path = op["path"]
                try:
                    if "existed_before" not in op and op.get("before_bytes") is None:
                        continue
                    if not op.get("existed_before", False):
                        if path.exists():
                            path.unlink()
                    else:
                        before = op.get("before_bytes")
                        if before is None:
                            before = b""
                        path.parent.mkdir(parents=True, exist_ok=True)
                        _write_bytes_atomic(path, before)
                except Exception as e:
                    err = f"Failed to rollback JSON write {path}: {e}"
                    logger.error("%s", err)
                    errors.append(err)

        if self.backup_path:
            try:
                from transcriptx.core.utils.state_backup import restore_from_backup

                restore_from_backup(self.backup_path)
            except Exception as e:
                err = f"Failed to restore processing-state backup: {e}"
                logger.error("%s", err)
                errors.append(err)

        for parent in reversed(self._created_parents):
            try:
                if parent.exists() and parent.is_dir() and not any(parent.iterdir()):
                    parent.rmdir()
            except OSError as e:
                err = f"Failed to remove created parent {parent}: {e}"
                logger.error("%s", err)
                errors.append(err)

        self._current_op = None
        return RollbackResult(ok=not errors, errors=errors)
