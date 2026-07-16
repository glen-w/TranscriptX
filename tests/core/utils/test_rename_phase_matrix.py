"""Rename phase matrix — characterization of managed-rename FSM outcomes.

Status / phase truth table (normalized snapshots; timestamps, operation_id, and
absolute paths excluded):

| Injection | Status | transaction_committed | finalize_attempted | Notes |
|-----------|--------|----------------------|--------------------|-------|
| Prepared journal persist fail | blocked | False | False | No txn |
| Txn fail + complete rollback | failed_rolled_back | False | False | No finalize |
| Txn fail + incomplete rollback | failed_rollback_incomplete | False | False | No finalize |
| transaction_committed marker fail | committed_partial | True | False | Returns immediately |
| Finalize move fail | committed_partial | True | True | Reconcile still runs |
| Artifact-remap fail | committed_partial | True | True | Reconcile still runs |
| Finalize journal persist fail | committed_partial | True | * | Errors include journal_persist_failed |
| Slug conflict | committed_partial | True | * | error code slug_conflict |
| Cache invalidation fail | committed_partial | True | * | error code cache_invalidation_failed |
| Complete-marker persist fail | committed_partial | True | * | Disk done; journal incomplete |
| Repair lock fail | blocked | * | * | lock failed |
| Repair already complete | committed_complete | True | True | Idempotent |
| Prepared not_started | blocked | False | False | prepared_not_started |
| Prepared fully_committed | committed_* | True | * | Promotes then post-commit |
| Prepared partially_applied | blocked | False | False | prepared_phase_unrecoverable |
| Prepared ambiguous | blocked | False | False | prepared_phase_unrecoverable |

Ordering invariants:
- No finalize after transaction failure
- Transaction-marker persist failure returns immediately (no finalize/reconcile)
- Reconcile still runs after ordinary finalize errors
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from transcriptx.core.utils.rename.journal import (
    JournalPhase,
    PreparedOpStatus,
    RenameJournalRecord,
    classify_prepared_transaction,
    load_journal,
    new_operation_id,
    persist_journal,
)
from transcriptx.core.utils.rename.outcome import RenameManagedOutcome, RenameStatus
from transcriptx.core.utils.rename.pipeline import (
    rename_managed_transcript,
    repair_managed_rename,
)
from transcriptx.core.utils.rename_transaction import RenameTransaction
from transcriptx.core.utils.slug_manager import SlugConflictError

from tests.core.utils.test_rename_managed_contracts import _managed_env


def normalize_outcome(outcome: RenameManagedOutcome, *, root: Path) -> dict[str, Any]:
    """Normalized snapshot excluding timestamps, operation_id, and abs paths."""
    del root  # reserved for future path normalization
    return {
        "status": outcome.status.value,
        "transaction_attempted": outcome.transaction_attempted,
        "transaction_succeeded": outcome.transaction_succeeded,
        "transaction_committed": outcome.transaction_committed,
        "finalize_attempted": outcome.finalize_attempted,
        "finalize_succeeded": outcome.finalize_succeeded,
        "output_dir_move_completed": outcome.output_dir_move_completed,
        "artifact_remap_completed": outcome.artifact_remap_completed,
        "reconciliation_succeeded": outcome.reconciliation_succeeded,
        "audio_renamed": outcome.audio_renamed,
        "error_codes": [e.code for e in outcome.errors],
        "error_phases": [e.phase for e in outcome.errors],
        "warning_count": len(outcome.warnings),
        "old_basename": (
            Path(outcome.old_transcript_path).name
            if outcome.old_transcript_path
            else ""
        ),
        "new_basename": (
            Path(outcome.new_transcript_path).name
            if outcome.new_transcript_path
            else ""
        ),
    }


def normalize_journal(record: RenameJournalRecord | None) -> dict[str, Any] | None:
    if record is None:
        return None
    return {
        "phase": record.phase,
        "error_codes": [e.get("code") for e in record.errors],
        "output_dir_move_completed": record.output_dir_move_completed,
        "artifact_remap_completed": record.artifact_remap_completed,
    }


class _LockDenied:
    acquired = False

    def __enter__(self) -> "_LockDenied":
        return self

    def __exit__(self, *_exc) -> bool:
        return False


def test_prepared_journal_persist_failure_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _managed_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "transcriptx.core.utils.rename.journal.persist_journal",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("prepared persist boom")),
    )
    outcome = rename_managed_transcript(env["transcript"], "renamed")
    snap = normalize_outcome(outcome, root=tmp_path)
    assert snap["status"] == RenameStatus.blocked.value
    assert snap["transaction_committed"] is False
    assert snap["finalize_attempted"] is False
    assert "journal_persist_failed" in snap["error_codes"]
    assert env["transcript"].exists()


def test_txn_failure_complete_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _managed_env(tmp_path, monkeypatch)
    original = env["transcript"].read_text(encoding="utf-8")
    real_json = RenameTransaction._execute_json_write
    calls = {"n": 0}

    def fail_once(self, op):
        calls["n"] += 1
        if calls["n"] == 1:
            return False, "json_write_failed", "simulated"
        return real_json(self, op)

    monkeypatch.setattr(RenameTransaction, "_execute_json_write", fail_once)
    outcome = rename_managed_transcript(env["transcript"], "new_name")
    snap = normalize_outcome(outcome, root=tmp_path)
    assert snap["status"] == RenameStatus.failed_rolled_back.value
    assert snap["transaction_committed"] is False
    assert snap["finalize_attempted"] is False
    assert env["transcript"].exists()
    assert env["transcript"].read_text(encoding="utf-8") == original


def test_txn_failure_incomplete_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _managed_env(tmp_path, monkeypatch)
    real_json = RenameTransaction._execute_json_write
    real_rollback = RenameTransaction.rollback
    calls = {"n": 0}

    def fail_once(self, op):
        calls["n"] += 1
        if calls["n"] == 1:
            return False, "json_write_failed", "simulated"
        return real_json(self, op)

    def broken_rollback(self):
        result = real_rollback(self)
        result.ok = False
        result.errors.append("simulated incomplete rollback")
        return result

    monkeypatch.setattr(RenameTransaction, "_execute_json_write", fail_once)
    monkeypatch.setattr(RenameTransaction, "rollback", broken_rollback)
    outcome = rename_managed_transcript(env["transcript"], "new_name")
    snap = normalize_outcome(outcome, root=tmp_path)
    assert snap["status"] == RenameStatus.failed_rollback_incomplete.value
    assert snap["transaction_committed"] is False
    assert snap["finalize_attempted"] is False


def test_transaction_committed_marker_persist_failure_returns_immediately(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _managed_env(tmp_path, monkeypatch)
    real_persist = persist_journal
    calls = {"n": 0}
    finalize_calls = {"n": 0}

    def flaky_persist(record):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("marker persist boom")
        return real_persist(record)

    def track_finalize(*a, **k):
        finalize_calls["n"] += 1
        from transcriptx.core.utils.rename.finalize import (
            finalize_output_directory_move as real,
        )

        return real(*a, **k)

    monkeypatch.setattr(
        "transcriptx.core.utils.rename.journal.persist_journal", flaky_persist
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.rename.finalize_phase.finalize_output_directory_move",
        track_finalize,
    )
    outcome = rename_managed_transcript(env["transcript"], "after_marker_fail")
    snap = normalize_outcome(outcome, root=tmp_path)
    assert snap["status"] == RenameStatus.committed_partial.value
    assert snap["transaction_committed"] is True
    assert snap["finalize_attempted"] is False
    assert finalize_calls["n"] == 0
    assert "journal_persist_failed" in snap["error_codes"]


def test_finalize_move_failure_still_reconciles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _managed_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "transcriptx.core.utils.rename.finalize_phase.finalize_output_directory_move",
        lambda *a, **k: (_ for _ in ()).throw(OSError("finalize boom")),
    )
    outcome = rename_managed_transcript(env["transcript"], "partial_fin")
    snap = normalize_outcome(outcome, root=tmp_path)
    assert snap["status"] == RenameStatus.committed_partial.value
    assert snap["transaction_committed"] is True
    assert snap["finalize_attempted"] is True
    assert "output_dir_move_failed" in snap["error_codes"]
    assert outcome.operation_id
    record = load_journal(outcome.operation_id)
    assert record is not None
    assert record.phase == JournalPhase.reconciled.value


def test_artifact_remap_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _managed_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "transcriptx.core.utils.rename.finalize_phase.execute_artifact_remap",
        lambda *_a, **_k: ["remap simulated failure"],
    )
    outcome = rename_managed_transcript(env["transcript"], "remap_fail")
    snap = normalize_outcome(outcome, root=tmp_path)
    assert snap["status"] == RenameStatus.committed_partial.value
    assert snap["transaction_committed"] is True
    assert "artifact_remap_failed" in snap["error_codes"]
    assert outcome.operation_id
    record = load_journal(outcome.operation_id)
    assert record is not None
    assert record.phase == JournalPhase.reconciled.value


def test_finalize_journal_persist_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _managed_env(tmp_path, monkeypatch)
    real_persist = persist_journal
    calls = {"n": 0}

    def flaky(record):
        calls["n"] += 1
        if calls["n"] == 3:
            raise OSError("finalize journal boom")
        return real_persist(record)

    monkeypatch.setattr("transcriptx.core.utils.rename.journal.persist_journal", flaky)
    outcome = rename_managed_transcript(env["transcript"], "fin_j_fail")
    snap = normalize_outcome(outcome, root=tmp_path)
    assert snap["status"] == RenameStatus.committed_partial.value
    assert snap["transaction_committed"] is True
    assert "journal_persist_failed" in snap["error_codes"]


def test_slug_conflict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = _managed_env(tmp_path, monkeypatch)

    def boom(*_a, **_k):
        raise SlugConflictError("slug collision simulated")

    monkeypatch.setattr(
        "transcriptx.core.utils.slug_manager.update_index_after_transcript_rename",
        boom,
    )
    outcome = rename_managed_transcript(env["transcript"], "slug_bad")
    snap = normalize_outcome(outcome, root=tmp_path)
    assert snap["status"] == RenameStatus.committed_partial.value
    assert "slug_conflict" in snap["error_codes"]
    assert snap["reconciliation_succeeded"] is False


def test_cache_invalidation_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _managed_env(tmp_path, monkeypatch)

    def boom(*_a, **_k):
        raise RuntimeError("cache boom")

    monkeypatch.setattr(
        "transcriptx.core.utils.rename.reconcile.invalidate_path_cache", boom
    )
    outcome = rename_managed_transcript(env["transcript"], "cache_bad")
    snap = normalize_outcome(outcome, root=tmp_path)
    assert snap["status"] == RenameStatus.committed_partial.value
    assert "cache_invalidation_failed" in snap["error_codes"]
    assert snap["reconciliation_succeeded"] is False


def test_complete_marker_persist_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _managed_env(tmp_path, monkeypatch)
    real_persist = persist_journal

    def flaky(record):
        if record.phase == JournalPhase.complete.value:
            raise OSError("complete marker boom")
        return real_persist(record)

    monkeypatch.setattr("transcriptx.core.utils.rename.journal.persist_journal", flaky)
    outcome = rename_managed_transcript(env["transcript"], "complete_fail")
    snap = normalize_outcome(outcome, root=tmp_path)
    assert snap["status"] == RenameStatus.committed_partial.value
    assert snap["transaction_committed"] is True
    assert "journal_persist_failed" in snap["error_codes"]
    assert (env["transcripts"] / "complete_fail.json").exists()


def test_repair_lock_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    monkeypatch.setattr("transcriptx.core.utils.rename.journal.STATE_DIR", state_dir)
    dest = tmp_path / "b.json"
    dest.write_text("{}", encoding="utf-8")
    op_id = new_operation_id()
    persist_journal(
        RenameJournalRecord(
            operation_id=op_id,
            phase=JournalPhase.transaction_committed.value,
            old_transcript_path=str(tmp_path / "a.json"),
            new_transcript_path=str(dest),
            transaction_file_renames=[
                [str(tmp_path / "a.json"), str(dest), "rename transcript"]
            ],
        )
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.rename.repair.FileLock",
        lambda *a, **k: _LockDenied(),
    )
    outcome = repair_managed_rename(op_id)
    snap = normalize_outcome(outcome, root=tmp_path)
    assert snap["status"] == RenameStatus.blocked.value
    assert "lock" in (outcome.last_error or "").lower()


@pytest.mark.parametrize(
    "phase",
    [
        JournalPhase.prepared.value,
        JournalPhase.transaction_committed.value,
        JournalPhase.finalized.value,
        JournalPhase.reconciled.value,
        JournalPhase.complete.value,
    ],
)
def test_repair_from_every_journal_phase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    monkeypatch.setattr("transcriptx.core.utils.rename.journal.STATE_DIR", state_dir)
    src = tmp_path / "a.json"
    dest = tmp_path / "b.json"
    dest.write_text("{}", encoding="utf-8")
    op_id = new_operation_id()
    persist_journal(
        RenameJournalRecord(
            operation_id=op_id,
            phase=phase,
            old_transcript_path=str(src),
            new_transcript_path=str(dest),
            transaction_file_renames=[[str(src), str(dest), "rename transcript"]],
            needs_output_dir_move=False,
            output_dir_move_completed=True,
            artifact_remap_completed=True,
        )
    )
    outcome = repair_managed_rename(op_id)
    snap = normalize_outcome(outcome, root=tmp_path)
    if phase == JournalPhase.complete.value:
        assert snap["status"] == RenameStatus.committed_complete.value
    elif phase == JournalPhase.prepared.value:
        assert snap["transaction_committed"] is True or snap["status"] == (
            RenameStatus.blocked.value
        )
    else:
        assert snap["status"] in {
            RenameStatus.committed_complete.value,
            RenameStatus.committed_partial.value,
            RenameStatus.blocked.value,
        }


@pytest.mark.parametrize(
    "classification,src_exists,dest_exists,expected_code",
    [
        (PreparedOpStatus.not_started, True, False, "prepared_not_started"),
        (PreparedOpStatus.fully_committed, False, True, None),
        (
            PreparedOpStatus.partially_applied,
            False,
            False,
            "prepared_phase_unrecoverable",
        ),
        (PreparedOpStatus.ambiguous, True, True, "prepared_phase_unrecoverable"),
    ],
)
def test_prepared_op_status_classifications(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    classification: PreparedOpStatus,
    src_exists: bool,
    dest_exists: bool,
    expected_code: str | None,
) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    monkeypatch.setattr("transcriptx.core.utils.rename.journal.STATE_DIR", state_dir)
    src = tmp_path / "a.json"
    dest = tmp_path / "b.json"
    if src_exists:
        src.write_text("{}", encoding="utf-8")
    if dest_exists:
        dest.write_text("{}", encoding="utf-8")
    record = RenameJournalRecord(
        operation_id=new_operation_id(),
        phase=JournalPhase.prepared.value,
        old_transcript_path=str(src),
        new_transcript_path=str(dest),
        transaction_file_renames=[[str(src), str(dest), "rename transcript"]],
    )
    assert classify_prepared_transaction(record) == classification
    persist_journal(record)
    outcome = repair_managed_rename(record.operation_id)
    if expected_code is None:
        assert outcome.transaction_committed is True or outcome.status in {
            RenameStatus.committed_complete,
            RenameStatus.committed_partial,
        }
    else:
        assert outcome.status == RenameStatus.blocked
        assert any(e.code == expected_code for e in outcome.errors)


def test_already_complete_repair_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    monkeypatch.setattr("transcriptx.core.utils.rename.journal.STATE_DIR", state_dir)
    dest = tmp_path / "b.json"
    dest.write_text("{}", encoding="utf-8")
    op_id = new_operation_id()
    persist_journal(
        RenameJournalRecord(
            operation_id=op_id,
            phase=JournalPhase.complete.value,
            old_transcript_path=str(tmp_path / "a.json"),
            new_transcript_path=str(dest),
        )
    )
    first = repair_managed_rename(op_id)
    second = repair_managed_rename(op_id)
    assert normalize_outcome(first, root=tmp_path) == normalize_outcome(
        second, root=tmp_path
    )
    assert first.status == RenameStatus.committed_complete
    assert first.message == "Rename operation already complete"


def test_happy_path_committed_complete_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _managed_env(tmp_path, monkeypatch)
    outcome = rename_managed_transcript(env["transcript"], "happy")
    snap = normalize_outcome(outcome, root=tmp_path)
    # Advisory warnings may be present; lock status/flags/errors only.
    assert snap["status"] == RenameStatus.committed_complete.value
    assert snap["transaction_attempted"] is True
    assert snap["transaction_succeeded"] is True
    assert snap["transaction_committed"] is True
    assert snap["finalize_attempted"] is True
    assert snap["finalize_succeeded"] is True
    assert snap["output_dir_move_completed"] is True
    assert snap["artifact_remap_completed"] is True
    assert snap["reconciliation_succeeded"] is True
    assert snap["audio_renamed"] is False
    assert snap["error_codes"] == []
    assert snap["error_phases"] == []
    assert snap["old_basename"] == "old_name.json"
    assert snap["new_basename"] == "happy.json"
    assert outcome.operation_id
    assert normalize_journal(load_journal(outcome.operation_id)) == {
        "phase": JournalPhase.complete.value,
        "error_codes": [],
        "output_dir_move_completed": True,
        "artifact_remap_completed": True,
    }
