"""Deeper bulk-deletion service coverage: groups, noop, retry, auth edges."""

from __future__ import annotations

import os
import threading
import uuid
from pathlib import Path


from transcriptx.core.utils.run_writer_locks import per_run_lock
from transcriptx.web.services.run_cleanup import (
    CONFIRM_DELETE_ALL,
    CONFIRM_DELETE_OLD,
    CleanupAuthorization,
    CleanupMode,
    CleanupStatus,
    RunCleanupService,
    TargetStatus,
)
from transcriptx.web.services.run_cleanup import faults
from transcriptx.web.services.run_cleanup import handles as handle_store
from transcriptx.web.services.run_cleanup import journal as cleanup_journal


def _mk_run(root: Path, slug: str, run_id: str, content: str = "x") -> Path:
    run = root / slug / run_id
    run.mkdir(parents=True, exist_ok=True)
    (run / "artifact.txt").write_text(content, encoding="utf-8")
    return run


def _svc(tmp_path: Path, **kwargs) -> RunCleanupService:
    out = kwargs.pop("outputs_dir", tmp_path / "outputs")
    out.mkdir(parents=True, exist_ok=True)
    groups = kwargs.pop("group_outputs_dir", out / "groups")
    groups.mkdir(parents=True, exist_ok=True)
    state = kwargs.pop("state_dir", tmp_path / "state")
    state.mkdir(parents=True, exist_ok=True)
    data = kwargs.pop("data_dir", tmp_path / "data")
    data.mkdir(parents=True, exist_ok=True)
    for name in ("transcripts", "recordings", "corrections", "groups"):
        (data / name).mkdir(exist_ok=True)
    (data / "transcripts" / "metadata").mkdir(parents=True, exist_ok=True)
    return RunCleanupService(
        outputs_dir=out,
        group_outputs_dir=groups,
        state_dir=state,
        project_root=tmp_path,
        data_dir=data,
        config_dir=tmp_path / "config",
        **kwargs,
    )


def _auth(mode: CleanupMode, plan_id: str) -> CleanupAuthorization:
    phrase = (
        CONFIRM_DELETE_ALL if mode is CleanupMode.DELETE_ALL else CONFIRM_DELETE_OLD
    )
    return CleanupAuthorization(
        acknowledged=True,
        phrase=phrase,
        mode=mode,
        plan_id=plan_id,
    )


class TestBulkGroupAndMixed:
    def test_delete_all_removes_group_and_transcript_runs(self, tmp_path):
        svc = _svc(tmp_path)
        gid = str(uuid.UUID("11111111-2222-4333-8444-555555555555"))
        t_run = _mk_run(svc.outputs_dir, "slug_mix", "20200101_000000_00000001")
        g_run = _mk_run(svc.group_outputs_dir, gid, "20200101_000000_00000002")
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")
        assert preview.run_count == 2
        assert preview.transcript_subjects == 1
        assert preview.group_subjects == 1
        result = svc.execute_cleanup(
            handle, _auth(CleanupMode.DELETE_ALL, preview.plan_id), "s1"
        )
        assert result.status is CleanupStatus.SUCCESS
        assert result.physically_deleted_count == 2
        assert not t_run.exists()
        assert not g_run.exists()
        # Empty subject parents pruned when possible
        assert not (svc.outputs_dir / "slug_mix").exists()
        assert not (svc.group_outputs_dir / gid).exists()

    def test_delete_old_independent_across_transcript_and_group(self, tmp_path):
        svc = _svc(tmp_path)
        gid = str(uuid.UUID("aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"))
        old_t = _mk_run(svc.outputs_dir, "slug_ind", "20200101_000000_00000001", "ot")
        new_t = _mk_run(svc.outputs_dir, "slug_ind", "20200101_000000_00000002", "nt")
        old_g = _mk_run(svc.group_outputs_dir, gid, "20200101_000000_00000003", "og")
        new_g = _mk_run(svc.group_outputs_dir, gid, "20200101_000000_00000004", "ng")
        os.utime(old_t, (1_000_000, 1_000_000))
        os.utime(new_t, (2_000_000, 2_000_000))
        os.utime(old_g, (1_000_000, 1_000_000))
        os.utime(new_g, (2_000_000, 2_000_000))
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_OLD, "s1")
        assert preview.run_count == 2
        assert len(preview.retained) == 2
        result = svc.execute_cleanup(
            handle, _auth(CleanupMode.DELETE_OLD, preview.plan_id), "s1"
        )
        assert result.status is CleanupStatus.SUCCESS
        assert not old_t.exists() and new_t.exists()
        assert not old_g.exists() and new_g.exists()


class TestBulkEdgeCases:
    def test_empty_workspace_is_noop_success_path(self, tmp_path):
        svc = _svc(tmp_path)
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")
        assert preview.run_count == 0
        assert preview.can_execute is True
        result = svc.execute_cleanup(
            handle, _auth(CleanupMode.DELETE_ALL, preview.plan_id), "s1"
        )
        assert result.status is CleanupStatus.NOOP
        assert result.visible_removed_count == 0
        assert result.physically_deleted_count == 0

    def test_wrong_session_cannot_claim_handle(self, tmp_path):
        svc = _svc(tmp_path)
        _mk_run(svc.outputs_dir, "slug_sess", "20200101_000000_00000001")
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "owner")
        result = svc.execute_cleanup(
            handle, _auth(CleanupMode.DELETE_ALL, preview.plan_id), "intruder"
        )
        assert result.status is CleanupStatus.BLOCKED
        assert (svc.outputs_dir / "slug_sess" / "20200101_000000_00000001").exists()

    def test_wrong_plan_id_blocks_and_consumes_handle(self, tmp_path):
        svc = _svc(tmp_path)
        _mk_run(svc.outputs_dir, "slug_plan", "20200101_000000_00000001")
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")
        bad = CleanupAuthorization(
            acknowledged=True,
            phrase=CONFIRM_DELETE_ALL,
            mode=CleanupMode.DELETE_ALL,
            plan_id="not-the-plan",
        )
        r1 = svc.execute_cleanup(handle, bad, "s1")
        assert r1.status is CleanupStatus.BLOCKED
        r2 = svc.execute_cleanup(
            handle, _auth(CleanupMode.DELETE_ALL, preview.plan_id), "s1"
        )
        assert r2.status is CleanupStatus.ALREADY_EXECUTED
        assert (svc.outputs_dir / "slug_plan" / "20200101_000000_00000001").exists()

    def test_mode_mismatch_phrase_blocks(self, tmp_path):
        svc = _svc(tmp_path)
        _mk_run(svc.outputs_dir, "slug_mode", "20200101_000000_00000001")
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_OLD, "s1")
        bad = CleanupAuthorization(
            acknowledged=True,
            phrase=CONFIRM_DELETE_ALL,
            mode=CleanupMode.DELETE_OLD,
            plan_id=preview.plan_id,
        )
        result = svc.execute_cleanup(handle, bad, "s1")
        assert result.status is CleanupStatus.BLOCKED
        assert (svc.outputs_dir / "slug_mode" / "20200101_000000_00000001").exists()

    def test_blocked_roots_prevent_execute(self, tmp_path):
        # Point outputs at protected transcripts tree
        data = tmp_path / "data"
        data.mkdir()
        transcripts = data / "transcripts"
        transcripts.mkdir()
        (data / "recordings").mkdir()
        (data / "corrections").mkdir()
        (data / "groups").mkdir()
        (transcripts / "metadata").mkdir()
        outputs = transcripts / "nested_out"
        outputs.mkdir()
        groups = tmp_path / "groups_out"
        groups.mkdir()
        state = tmp_path / "state"
        state.mkdir()
        svc = RunCleanupService(
            outputs_dir=outputs,
            group_outputs_dir=groups,
            state_dir=state,
            project_root=tmp_path,
            data_dir=data,
            config_dir=tmp_path / "config",
        )
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")
        assert preview.can_execute is False
        assert preview.blocking_errors
        result = svc.execute_cleanup(
            handle, _auth(CleanupMode.DELETE_ALL, preview.plan_id), "s1"
        )
        assert result.status is CleanupStatus.BLOCKED

    def test_delete_all_locked_skip_is_partial(self, tmp_path):
        svc = _svc(tmp_path)
        run_a = _mk_run(svc.outputs_dir, "slug_a", "20200101_000000_00000001")
        run_b = _mk_run(svc.outputs_dir, "slug_b", "20200101_000000_00000002")
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")
        held = threading.Event()
        release = threading.Event()
        result_box: list = []

        def holder():
            with per_run_lock(run_a, state_dir=svc.state_dir):
                held.set()
                release.wait(timeout=10)

        def executor():
            assert held.wait(timeout=5)
            result_box.append(
                svc.execute_cleanup(
                    handle, _auth(CleanupMode.DELETE_ALL, preview.plan_id), "s1"
                )
            )
            release.set()

        t1 = threading.Thread(target=holder)
        t2 = threading.Thread(target=executor)
        t1.start()
        t2.start()
        t2.join(timeout=15)
        t1.join(timeout=15)
        result = result_box[0]
        assert result.status is CleanupStatus.PARTIAL
        assert any(t.status is TargetStatus.LOCKED_SKIP for t in result.targets)
        assert run_a.exists()
        assert not run_b.exists()

    def test_external_disappear_before_execute_is_stale(self, tmp_path):
        svc = _svc(tmp_path)
        run = _mk_run(svc.outputs_dir, "slug_gone", "20200101_000000_00000001")
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")
        # Remove the run between preview and execute
        for child in run.iterdir():
            child.unlink()
        run.rmdir()
        (svc.outputs_dir / "slug_gone").rmdir()
        result = svc.execute_cleanup(
            handle, _auth(CleanupMode.DELETE_ALL, preview.plan_id), "s1"
        )
        assert result.status is CleanupStatus.STALE_PLAN
        assert result.visible_removed_count == 0

    def test_retry_invalid_operation_id_blocked(self, tmp_path):
        svc = _svc(tmp_path)
        result = svc.retry_interrupted_staging("not-valid")
        assert result.status is CleanupStatus.BLOCKED
        assert any("Invalid operation_id" in e for e in result.errors)

    def test_retry_missing_journal_blocked(self, tmp_path):
        svc = _svc(tmp_path)
        result = svc.retry_interrupted_staging("1_abcdefabcdef")
        assert result.status is CleanupStatus.BLOCKED
        assert any("Unknown operation" in e for e in result.errors)

    def test_retry_completes_interrupted_staging(self, tmp_path):
        svc = _svc(tmp_path)
        run = _mk_run(svc.outputs_dir, "slug_retry", "20200101_000000_00000001")
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")

        def boom():
            raise RuntimeError("stop after rename for retry test")

        faults.set_fault_hook("after_first_rename", boom)
        try:
            partial = svc.execute_cleanup(
                handle, _auth(CleanupMode.DELETE_ALL, preview.plan_id), "s1"
            )
        finally:
            faults.clear_fault_hooks()

        assert partial.status is CleanupStatus.PARTIAL
        assert not run.exists()
        assert partial.operation_id
        pending = cleanup_journal.list_pending_staging(svc.state_dir)
        assert pending, "expected staged remnant in journal"

        retry = svc.retry_interrupted_staging(partial.operation_id)
        assert retry.status in {CleanupStatus.SUCCESS, CleanupStatus.PARTIAL}
        assert retry.physically_deleted_count >= 1
        # Staging for that operation should be gone
        staging_root = svc.outputs_dir / ".cleanup_staging" / partial.operation_id
        assert not staging_root.exists() or not any(staging_root.iterdir())

    def test_protected_path_getter_override_blocks(self, tmp_path):
        svc = _svc(tmp_path)
        # Getter returns outputs itself as protected → overlap blocks
        out = svc.outputs_dir

        def getter():
            return {"dangerous": out}

        svc2 = RunCleanupService(
            outputs_dir=out,
            group_outputs_dir=svc.group_outputs_dir,
            state_dir=svc.state_dir,
            project_root=tmp_path,
            data_dir=svc.data_dir,
            config_dir=tmp_path / "config",
            protected_path_getter=getter,
        )
        _mk_run(out, "slug_prot", "20200101_000000_00000001")
        handle, preview = svc2.preview_cleanup(CleanupMode.DELETE_ALL, "s1")
        assert preview.can_execute is False
        result = svc2.execute_cleanup(
            handle, _auth(CleanupMode.DELETE_ALL, preview.plan_id), "s1"
        )
        assert result.status is CleanupStatus.BLOCKED
        assert (out / "slug_prot" / "20200101_000000_00000001").exists()

    def test_handle_session_isolation_after_success(self, tmp_path):
        handle_store._reset_for_tests()
        try:
            svc = _svc(tmp_path)
            _mk_run(svc.outputs_dir, "slug_iso", "20200101_000000_00000001")
            handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")
            result = svc.execute_cleanup(
                handle, _auth(CleanupMode.DELETE_ALL, preview.plan_id), "s1"
            )
            assert result.status is CleanupStatus.SUCCESS
            # Same token different session must not see completed result as executable
            again = svc.execute_cleanup(
                handle, _auth(CleanupMode.DELETE_ALL, preview.plan_id), "other"
            )
            assert again.status in {
                CleanupStatus.BLOCKED,
                CleanupStatus.ALREADY_EXECUTED,
            }
        finally:
            handle_store._reset_for_tests()
