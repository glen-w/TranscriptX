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
    """Point the module at a granting lock; pass explicit state file to txn."""
    state_file = tmp_path / "processing_state.json"
    monkeypatch.setattr(rt, "FileLock", lambda *a, **k: _FakeLock(acquired=True))
    return state_file


@pytest.mark.unit
def test_rename_transaction_dry_run_execute_logs_ops_only() -> None:
    tx = RenameTransaction(dry_run=True, processing_state_file=Path("/tmp/x"))
    tx.add_rename(Path("a.txt"), Path("b.txt"), "move transcript")
    result = tx.execute()
    assert result.ok is True
    assert len(tx.operations) == 1
    assert tx.executed == []


@pytest.mark.unit
def test_add_state_update_records_operation(patched_state) -> None:
    tx = RenameTransaction(dry_run=True, processing_state_file=patched_state)

    def bump(x: list) -> None:
        x.append(1)

    acc: list = []
    tx.add_state_update(bump, acc)
    assert tx.operations[0]["type"] == "state_update"
    assert tx.execute().ok is True


@pytest.mark.unit
def test_execute_renames_file_and_records_executed(patched_state, tmp_path) -> None:
    source = tmp_path / "old.txt"
    source.write_text("data")
    dest = tmp_path / "nested" / "new.txt"

    tx = RenameTransaction(processing_state_file=patched_state)
    tx.add_rename(source, dest, "rename")

    assert tx.execute().ok is True
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

    tx = RenameTransaction(processing_state_file=patched_state)
    tx.add_rename(source, dest)
    tx.add_state_update(lambda value: calls.append(value), "done")

    assert tx.execute().ok is True
    assert calls == ["done"]
    assert len(tx.executed) == 2


@pytest.mark.unit
def test_execute_rolls_back_when_dest_exists(patched_state, tmp_path) -> None:
    src1 = tmp_path / "a.txt"
    src1.write_text("a")
    dst1 = tmp_path / "a_renamed.txt"

    src2 = tmp_path / "b.txt"
    src2.write_text("b")
    dst2 = tmp_path / "occupied.txt"
    dst2.write_text("existing")

    tx = RenameTransaction(processing_state_file=patched_state)
    tx.add_rename(src1, dst1)
    tx.add_rename(src2, dst2)

    result = tx.execute()
    assert result.ok is False
    assert result.rollback is not None
    assert result.rollback.ok is True
    assert src1.exists()
    assert not dst1.exists()


@pytest.mark.unit
def test_execute_fails_when_lock_not_acquired(monkeypatch, tmp_path) -> None:
    state_file = tmp_path / "processing_state.json"
    monkeypatch.setattr(rt, "FileLock", lambda *a, **k: _FakeLock(acquired=False))

    source = tmp_path / "old.txt"
    source.write_text("data")

    tx = RenameTransaction(processing_state_file=state_file)
    tx.add_rename(source, tmp_path / "new.txt")

    result = tx.execute()
    assert result.ok is False
    assert result.failure_code == "lock_failed"
    assert source.exists()


@pytest.mark.unit
def test_execute_unknown_operation_type_fails(patched_state, tmp_path) -> None:
    tx = RenameTransaction(processing_state_file=patched_state)
    tx.operations.append({"type": "bogus", "executed": False})
    assert tx.execute().ok is False


@pytest.mark.unit
def test_internal_rename_source_missing_returns_false(tmp_path) -> None:
    tx = RenameTransaction(processing_state_file=tmp_path / "state.json")
    op = {
        "source": tmp_path / "missing.txt",
        "dest": tmp_path / "out.txt",
        "temp": None,
    }
    ok, code, _msg = tx._execute_rename(op)
    assert ok is False
    assert code == "source_missing"


@pytest.mark.unit
def test_internal_state_update_exception_returns_false() -> None:
    tx = RenameTransaction(processing_state_file=Path("/tmp/x"))

    def boom() -> None:
        raise RuntimeError("nope")

    op = {"func": boom, "args": (), "kwargs": {}}
    ok, code, _msg = tx._execute_state_update(op)
    assert ok is False
    assert code == "state_update_failed"


@pytest.mark.unit
def test_rollback_reverses_executed_renames(tmp_path) -> None:
    source = tmp_path / "orig.txt"
    dest = tmp_path / "moved.txt"
    dest.write_text("payload")

    tx = RenameTransaction(processing_state_file=tmp_path / "state.json")
    tx.executed.append(
        {
            "type": "rename",
            "source": source,
            "dest": dest,
            "executed": True,
            "temp": None,
        }
    )

    result = tx.rollback()
    assert result.ok is True
    assert source.exists()
    assert not dest.exists()


@pytest.mark.unit
def test_case_only_second_move_failure_restores_source(
    monkeypatch, patched_state, tmp_path
):
    """Item 66: first case-only move succeeds, second fails → restore original."""
    source = tmp_path / "old_name.txt"
    source.write_text("data")
    dest = tmp_path / "NEW_NAME.txt"

    monkeypatch.setattr(
        rt,
        "paths_are_case_only_rename",
        lambda a, b: True,
    )

    real_rename = Path.rename
    calls = {"n": 0}

    def flaky_rename(self, target):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("simulated second-move failure")
        return real_rename(self, target)

    monkeypatch.setattr(Path, "rename", flaky_rename)

    tx = RenameTransaction(processing_state_file=patched_state)
    tx.add_rename(source, dest, "case-only")
    result = tx.execute()
    assert result.ok is False
    assert result.failure_code == "case_only_second_move_failed"
    assert result.rollback is not None
    assert result.rollback.ok is True
    assert source.exists()
    assert source.read_text() == "data"
    # Destination must not remain as the committed name after rollback
    if dest.exists() and dest.resolve() != source.resolve():
        raise AssertionError("dest left behind after rollback")


@pytest.mark.unit
def test_rollback_failure_surfaces_structured_errors(
    monkeypatch, patched_state, tmp_path
):
    """Item 67: rollback failure is not silently treated as clean rollback."""
    src1 = tmp_path / "a.txt"
    src1.write_text("a")
    dst1 = tmp_path / "a_renamed.txt"

    src2 = tmp_path / "b.txt"
    src2.write_text("b")
    dst2 = tmp_path / "occupied.txt"
    dst2.write_text("existing")

    tx = RenameTransaction(processing_state_file=patched_state)
    tx.add_rename(src1, dst1)
    tx.add_rename(src2, dst2)

    real_rollback = RenameTransaction.rollback

    def broken_rollback(self):
        result = real_rollback(self)
        result.ok = False
        result.errors.append("injected rollback failure")
        return result

    monkeypatch.setattr(RenameTransaction, "rollback", broken_rollback)
    result = tx.execute()
    assert result.ok is False
    assert result.rollback is not None
    assert result.rollback.ok is False
    assert "injected rollback failure" in result.rollback.errors


@pytest.mark.unit
def test_zero_byte_json_before_image_restored(patched_state, tmp_path):
    """Item 68: existing zero-byte file is not treated as newly created."""
    target = tmp_path / "sidecar.json"
    target.write_bytes(b"")

    tx = RenameTransaction(processing_state_file=patched_state)
    tx.add_json_write(target, {"ok": True}, description="write")

    missing = tmp_path / "missing_src.txt"
    tx.add_rename(missing, tmp_path / "x.txt")

    result = tx.execute()
    assert result.ok is False
    assert result.rollback is not None
    assert target.exists()
    assert target.read_bytes() == b""
