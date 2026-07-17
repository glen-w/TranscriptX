"""Unit/integration tests for journal_ops extract (durability + op-id allocation)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from transcriptx.web.services.run_cleanup import journal
from transcriptx.web.services.run_cleanup import journal_ops
from transcriptx.web.services.run_cleanup.models import (
    CLEANUP_POLICY_VERSION,
    CleanupMode,
    CleanupPlan,
    CleanupTarget,
    EntryClassification,
    RootIdentity,
    SubjectType,
)


def _host(state_dir: Path, outputs_dir: Path | None = None) -> SimpleNamespace:
    out = outputs_dir or (state_dir.parent / "outputs")
    return SimpleNamespace(
        state_dir=state_dir,
        outputs_dir=out,
        group_outputs_dir=out / "groups",
    )


def _minimal_plan(
    tmp_path: Path, *, run_id: str = "20200101_000000_00000001"
) -> CleanupPlan:
    out = tmp_path / "outputs"
    out.mkdir(parents=True, exist_ok=True)
    canonical = out / "slug" / run_id
    canonical.mkdir(parents=True, exist_ok=True)
    target = CleanupTarget(
        subject_type=SubjectType.transcript,
        subject_id="slug",
        run_id=run_id,
        root_relative_path=f"slug/{run_id}",
        canonical_path=str(canonical.resolve()),
        mtime_ns=1,
        filesystem_dev=1,
        filesystem_ino=3,
        size_estimate_bytes=1,
        file_count=1,
        tree_fingerprint="a" * 64,
        safety_status=EntryClassification.eligible,
    )
    return CleanupPlan(
        plan_id="p",
        mode=CleanupMode.DELETE_ALL,
        policy_version=CLEANUP_POLICY_VERSION,
        created_at_iso="t",
        roots=(
            RootIdentity(
                kind=SubjectType.transcript,
                configured_path=str(out),
                canonical_path=str(out.resolve()),
                dev=1,
                ino=2,
                is_symlink=False,
            ),
        ),
        candidates=(target,),
        retained=(),
        exclusions=(),
        warnings=(),
        blocking_errors=(),
        can_execute=True,
    )


@pytest.mark.unit
class TestPersistTargetStateDurability:
    def test_exception_require_durable_false_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        host = _host(tmp_path / "state")

        def boom(*_a, **_k):
            raise RuntimeError("disk full")

        monkeypatch.setattr(journal, "update_target_state", boom)
        assert (
            journal_ops.persist_target_state(
                host,
                "1_abcdefabcdef",
                canonical_path="/x",
                state="staged",
                require_durable=False,
            )
            is None
        )

    def test_exception_require_durable_true_reraises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        host = _host(tmp_path / "state")

        def boom(*_a, **_k):
            raise RuntimeError("disk full")

        monkeypatch.setattr(journal, "update_target_state", boom)
        with pytest.raises(RuntimeError, match="disk full"):
            journal_ops.persist_target_state(
                host,
                "1_abcdefabcdef",
                canonical_path="/x",
                state="staged",
                require_durable=True,
            )

    def test_failed_fsync_require_durable_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        host = _host(tmp_path / "state")
        monkeypatch.setattr(
            journal,
            "update_target_state",
            lambda *_a, **_k: journal.DirFsyncResult(
                journal.DirFsyncOutcome.FAILED, "fsync boom"
            ),
        )
        with pytest.raises(journal.JournalDurabilityError, match="fsync boom"):
            journal_ops.persist_target_state(
                host,
                "1_abcdefabcdef",
                canonical_path="/x",
                state="staged",
                require_durable=True,
            )

    def test_failed_fsync_require_durable_false_returns_result(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        host = _host(tmp_path / "state")
        failed = journal.DirFsyncResult(journal.DirFsyncOutcome.FAILED, "fsync boom")
        monkeypatch.setattr(journal, "update_target_state", lambda *_a, **_k: failed)
        assert (
            journal_ops.persist_target_state(
                host,
                "1_abcdefabcdef",
                canonical_path="/x",
                state="staged",
                require_durable=False,
            )
            is failed
        )

    def test_unsupported_fsync_require_durable_true_returns(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """UNSUPPORTED is not a durability failure under require_durable."""
        host = _host(tmp_path / "state")
        unsupported = journal.DirFsyncResult(
            journal.DirFsyncOutcome.UNSUPPORTED, "no fsync"
        )
        monkeypatch.setattr(
            journal, "update_target_state", lambda *_a, **_k: unsupported
        )
        assert (
            journal_ops.persist_target_state(
                host,
                "1_abcdefabcdef",
                canonical_path="/x",
                state="staged",
                require_durable=True,
            )
            is unsupported
        )


@pytest.mark.unit
class TestNewJournaledOperation:
    def test_retries_on_file_exists_then_succeeds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        state = tmp_path / "state"
        state.mkdir()
        host = _host(state, tmp_path / "outputs")
        plan = _minimal_plan(tmp_path)
        ids = iter(["1_aaaaaaaaaaaa", "1_bbbbbbbbbbbb"])
        monkeypatch.setattr(journal, "new_operation_id", lambda: next(ids))
        calls = {"n": 0}

        def write_op(*_a, operation_id: str, **_k):
            calls["n"] += 1
            if operation_id == "1_aaaaaaaaaaaa":
                raise FileExistsError(operation_id)
            return state / "cleanup" / "operations" / f"{operation_id}.json"

        monkeypatch.setattr(journal, "write_operation", write_op)
        assert (
            journal_ops.new_journaled_operation(host, plan, list(plan.candidates))
            == "1_bbbbbbbbbbbb"
        )
        assert calls["n"] == 2

    def test_five_collisions_raise(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        state = tmp_path / "state"
        state.mkdir()
        host = _host(state, tmp_path / "outputs")
        plan = _minimal_plan(tmp_path)
        monkeypatch.setattr(journal, "new_operation_id", lambda: "1_cccccccccccc")
        monkeypatch.setattr(
            journal,
            "write_operation",
            lambda *_a, **_k: (_ for _ in ()).throw(FileExistsError("taken")),
        )
        with pytest.raises(RuntimeError, match="could not allocate operation_id"):
            journal_ops.new_journaled_operation(host, plan, list(plan.candidates))
