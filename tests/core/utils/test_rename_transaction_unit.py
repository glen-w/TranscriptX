"""RenameTransaction bookkeeping and execute/rollback behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.core.utils import rename_transaction as rt
from transcriptx.core.utils.rename_transaction import RenameTransaction


class _FakeLock:
    """Context-manager stand-in for FileLock that reports acquired state."""

    def __init__(self, *args, acquired: bool = True, **kwargs) -> None:
        self.acquired = acquired

    def __enter__(self) -> "_FakeLock":
        return self

    def __exit__(self, *exc) -> bool:
        return False


@pytest.fixture
def patched_state(monkeypatch, tmp_path):
    """Point the module at a missing state file and a granting lock."""
    state_file = tmp_path / "processing_state.json"
    monkeypatch.setattr(rt, "PROCESSING_STATE_FILE", state_file)
    monkeypatch.setattr(rt, "FileLock", lambda *a, **k: _FakeLock(acquired=True))
    return state_file


@pytest.mark.unit
def test_rename_transaction_dry_run_execute_logs_ops_only() -> None:
    tx = RenameTransaction(dry_run=True)
    tx.add_rename(Path("a.txt"), Path("b.txt"), "move transcript")
    assert tx.execute() is True
    assert len(tx.operations) == 1
    assert tx.executed == []


@pytest.mark.unit
def test_add_state_update_records_operation() -> None:
    tx = RenameTransaction(dry_run=True)

    def bump(x: list) -> None:
        x.append(1)

    acc: list = []
    tx.add_state_update(bump, acc)
    assert tx.operations[0]["type"] == "state_update"
    assert tx.execute() is True


@pytest.mark.unit
def test_execute_renames_file_and_records_executed(patched_state, tmp_path) -> None:
    source = tmp_path / "old.txt"
    source.write_text("data")
    dest = tmp_path / "nested" / "new.txt"

    tx = RenameTransaction()
    tx.add_rename(source, dest, "rename")

    assert tx.execute() is True
    assert dest.exists()
    assert not source.exists()
    assert len(tx.executed) == 1
    assert tx.operations[0]["executed"] is True


@pytest.mark.unit
def test_execute_runs_state_update(patched_state, tmp_path) -> None:
    source = tmp_path / "old.txt"
    source.write_text("data")
    dest = tmp_path / "new.txt"
    calls: list = []

    tx = RenameTransaction()
    tx.add_rename(source, dest)
    tx.add_state_update(lambda value: calls.append(value), "done")

    assert tx.execute() is True
    assert calls == ["done"]
    assert len(tx.executed) == 2


@pytest.mark.unit
def test_execute_rolls_back_when_dest_exists(patched_state, tmp_path) -> None:
    src1 = tmp_path / "a.txt"
    src1.write_text("a")
    dst1 = tmp_path / "a_renamed.txt"

    # Second rename will fail because its destination already exists.
    src2 = tmp_path / "b.txt"
    src2.write_text("b")
    dst2 = tmp_path / "occupied.txt"
    dst2.write_text("existing")

    tx = RenameTransaction()
    tx.add_rename(src1, dst1)
    tx.add_rename(src2, dst2)

    assert tx.execute() is False
    # First rename must be rolled back to its original location.
    assert src1.exists()
    assert not dst1.exists()


@pytest.mark.unit
def test_execute_fails_when_lock_not_acquired(monkeypatch, tmp_path) -> None:
    state_file = tmp_path / "processing_state.json"
    monkeypatch.setattr(rt, "PROCESSING_STATE_FILE", state_file)
    monkeypatch.setattr(rt, "FileLock", lambda *a, **k: _FakeLock(acquired=False))

    source = tmp_path / "old.txt"
    source.write_text("data")

    tx = RenameTransaction()
    tx.add_rename(source, tmp_path / "new.txt")

    assert tx.execute() is False
    assert source.exists()


@pytest.mark.unit
def test_execute_unknown_operation_type_fails(patched_state, tmp_path) -> None:
    tx = RenameTransaction()
    tx.operations.append({"type": "bogus", "executed": False})
    assert tx.execute() is False


@pytest.mark.unit
def test_internal_rename_source_missing_returns_false(tmp_path) -> None:
    tx = RenameTransaction()
    op = {"source": tmp_path / "missing.txt", "dest": tmp_path / "out.txt"}
    assert tx._execute_rename(op) is False


@pytest.mark.unit
def test_internal_state_update_exception_returns_false() -> None:
    tx = RenameTransaction()

    def boom() -> None:
        raise RuntimeError("nope")

    op = {"func": boom, "args": (), "kwargs": {}}
    assert tx._execute_state_update(op) is False


@pytest.mark.unit
def test_rollback_reverses_executed_renames(tmp_path) -> None:
    source = tmp_path / "orig.txt"
    dest = tmp_path / "moved.txt"
    dest.write_text("payload")

    tx = RenameTransaction()
    tx.executed.append(
        {"type": "rename", "source": source, "dest": dest, "executed": True}
    )

    tx.rollback()

    assert source.exists()
    assert not dest.exists()
