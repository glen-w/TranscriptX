"""Additional release-blocking tests for cleanup round 2."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from transcriptx.core.utils.run_writer_locks import (
    LockDirectoryUnsafeError,
    RunWriterLease,
    assert_lease_for_run,
    run_tree_mutation_gate,
    try_run_tree_mutation_gate,
)
from transcriptx.web.services.run_cleanup import (
    CLEANUP_BUSY,
    CONFIRM_DELETE_ALL,
    CleanupAuthorization,
    CleanupMode,
    CleanupStatus,
    RunCleanupService,
)
from transcriptx.web.services.run_cleanup.physical_delete import (
    PhysicalDeleteUnsafeError,
    VerifiedStagedTree,
    safe_rmtree_verified,
)
from transcriptx.web.services.run_cleanup.staging import (
    collision_proof_staging_basename,
)
from transcriptx.web.services.run_cleanup.models import (
    CleanupTarget,
    EntryClassification,
    SubjectType,
)


def _svc(tmp_path: Path) -> RunCleanupService:
    out = tmp_path / "outputs"
    out.mkdir(parents=True, exist_ok=True)
    groups = out / "groups"
    groups.mkdir(parents=True, exist_ok=True)
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    data = tmp_path / "data"
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
    )


def _mk_run(root: Path, slug: str, run_id: str) -> Path:
    run = root / slug / run_id
    run.mkdir(parents=True, exist_ok=True)
    (run / "artifact.txt").write_text("x", encoding="utf-8")
    return run


def test_forged_verified_staged_tree_rejected():
    with pytest.raises(PhysicalDeleteUnsafeError):
        VerifiedStagedTree(
            staging_path="/tmp/x",
            staged_dev=1,
            staged_ino=2,
            planned_filesystem_dev=1,
            content_tree_fingerprint="0" * 64,
            operation_id="1_abcdefabcdef",
            canonical_source_path="/tmp/src",
            subject_type="transcript",
            subject_id="s",
            run_id="r",
        )


def test_safe_rmtree_verified_rejects_forged_token(tmp_path):
    # Bypass __post_init__ via object.__new__
    proof = object.__new__(VerifiedStagedTree)
    object.__setattr__(proof, "staging_path", str(tmp_path))
    object.__setattr__(proof, "staged_dev", 1)
    object.__setattr__(proof, "staged_ino", 1)
    object.__setattr__(proof, "planned_filesystem_dev", 1)
    object.__setattr__(proof, "content_tree_fingerprint", "0" * 64)
    object.__setattr__(proof, "operation_id", "1_abcdefabcdef")
    object.__setattr__(proof, "canonical_source_path", "/x")
    object.__setattr__(proof, "subject_type", "transcript")
    object.__setattr__(proof, "subject_id", "s")
    object.__setattr__(proof, "run_id", "r")
    object.__setattr__(proof, "_token", object())
    with pytest.raises(PhysicalDeleteUnsafeError):
        safe_rmtree_verified(proof)


def test_staging_basename_collision_proof_across_kinds():
    t = CleanupTarget(
        subject_type=SubjectType.transcript,
        subject_id="same",
        run_id="20200101_000000_00000001",
        root_relative_path="same/20200101_000000_00000001",
        canonical_path="/outputs/same/20200101_000000_00000001",
        mtime_ns=1,
        filesystem_dev=1,
        filesystem_ino=2,
        size_estimate_bytes=1,
        file_count=1,
        tree_fingerprint="a" * 64,
        safety_status=EntryClassification.eligible,
    )
    g = CleanupTarget(
        subject_type=SubjectType.group,
        subject_id="same",
        run_id="20200101_000000_00000001",
        root_relative_path="same/20200101_000000_00000001",
        canonical_path="/groups/same/20200101_000000_00000001",
        mtime_ns=1,
        filesystem_dev=1,
        filesystem_ino=3,
        size_estimate_bytes=1,
        file_count=1,
        tree_fingerprint="b" * 64,
        safety_status=EntryClassification.eligible,
    )
    assert collision_proof_staging_basename(t) != collision_proof_staging_basename(g)


def test_unrelated_handle_gate_contention_is_cleanup_busy(tmp_path):
    svc = _svc(tmp_path)
    _mk_run(svc.outputs_dir, "slug_a", "20200101_000000_00000001")
    handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")
    auth = CleanupAuthorization(
        acknowledged=True,
        phrase=CONFIRM_DELETE_ALL,
        mode=CleanupMode.DELETE_ALL,
        plan_id=preview.plan_id,
    )
    held = threading.Event()
    release = threading.Event()
    result_box: list = []

    def holder():
        with run_tree_mutation_gate(state_dir=svc.state_dir):
            held.set()
            release.wait(timeout=10)

    def executor():
        assert held.wait(timeout=5)
        result_box.append(svc.execute_cleanup(handle, auth, "s1"))
        release.set()

    t1 = threading.Thread(target=holder)
    t2 = threading.Thread(target=executor)
    t1.start()
    t2.start()
    t2.join(timeout=15)
    t1.join(timeout=15)
    result = result_box[0]
    assert result.status is CleanupStatus.BLOCKED
    assert CLEANUP_BUSY in result.errors


def test_invalid_auth_consumes_handle(tmp_path):
    svc = _svc(tmp_path)
    _mk_run(svc.outputs_dir, "slug_b", "20200101_000000_00000001")
    handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")
    bad = CleanupAuthorization(
        acknowledged=True,
        phrase="DELETE ALL ",
        mode=CleanupMode.DELETE_ALL,
        plan_id=preview.plan_id,
    )
    r1 = svc.execute_cleanup(handle, bad, "s1")
    assert r1.status is CleanupStatus.BLOCKED
    r2 = svc.execute_cleanup(
        handle,
        CleanupAuthorization(
            acknowledged=True,
            phrase=CONFIRM_DELETE_ALL,
            mode=CleanupMode.DELETE_ALL,
            plan_id=preview.plan_id,
        ),
        "s1",
    )
    assert r2.status is CleanupStatus.ALREADY_EXECUTED


def test_symlinked_run_locks_dir_fails_closed(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    real = tmp_path / "real_locks"
    real.mkdir()
    link = state / "run_locks"
    link.symlink_to(real)
    from transcriptx.core.utils.run_writer_locks import try_per_run_lock

    with pytest.raises(LockDirectoryUnsafeError):
        try_per_run_lock(tmp_path / "run", state_dir=state)


def test_assert_lease_rejects_wrong_root():
    from transcriptx.core.utils.file_lock import LockAcquisitionError

    lease = RunWriterLease(canonical_run_root="/a/b", lock_file="/x.lock")
    with pytest.raises(LockAcquisitionError):
        assert_lease_for_run(lease, "/other")


def test_platform_unsupported_blocks_before_mutation(tmp_path, monkeypatch):
    from transcriptx.web.services.run_cleanup import PLATFORM_UNSUPPORTED, fd_ops

    monkeypatch.setattr(fd_ops, "_RENAMEAT_SUPPORTED", False)
    # Force re-check path: platform_supports reads cache
    monkeypatch.setattr(fd_ops, "platform_supports_secure_cleanup", lambda: False)
    svc = _svc(tmp_path)
    _mk_run(svc.outputs_dir, "slug_plat", "20200101_000000_00000001")
    handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")
    rename_count = {"n": 0}
    real_rename = __import__("os").rename

    def counting_rename(src, dst, *a, **k):
        rename_count["n"] += 1
        return real_rename(src, dst, *a, **k)

    monkeypatch.setattr(__import__("os"), "rename", counting_rename)
    result = svc.execute_cleanup(
        handle,
        CleanupAuthorization(
            acknowledged=True,
            phrase=CONFIRM_DELETE_ALL,
            mode=CleanupMode.DELETE_ALL,
            plan_id=preview.plan_id,
        ),
        "s1",
    )
    assert result.status is CleanupStatus.BLOCKED
    assert PLATFORM_UNSUPPORTED in result.errors
    assert rename_count["n"] == 0
    assert (svc.outputs_dir / "slug_plat" / "20200101_000000_00000001").exists()


def test_stage_outcome_invariants():
    from transcriptx.web.services.run_cleanup.models import (
        CleanupTarget,
        CleanupTargetResult,
        EntryClassification,
        StageOutcome,
        SubjectType,
        TargetStatus,
    )

    t = CleanupTarget(
        subject_type=SubjectType.transcript,
        subject_id="s",
        run_id="20200101_000000_00000001",
        root_relative_path="s/20200101_000000_00000001",
        canonical_path="/o/s/r",
        mtime_ns=1,
        filesystem_dev=1,
        filesystem_ino=2,
        size_estimate_bytes=1,
        file_count=1,
        tree_fingerprint="a" * 64,
        safety_status=EntryClassification.eligible,
    )
    tr = CleanupTargetResult(
        subject_type=t.subject_type,
        subject_id=t.subject_id,
        run_id=t.run_id,
        root_relative_path=t.root_relative_path,
        canonical_path=t.canonical_path,
        status=TargetStatus.STAGING_FAILED,
        message="x",
    )
    with pytest.raises(ValueError, match="visible_removed"):
        StageOutcome(
            target=t,
            staging_path=None,
            rename_attempted=False,
            visible_removed=True,
            staged_dev=None,
            staged_ino=None,
            journal_updated=False,
            deletion_ready=False,
            target_result=tr,
        )
    with pytest.raises(ValueError, match="deletion_ready"):
        StageOutcome(
            target=t,
            staging_path="/x",
            rename_attempted=True,
            visible_removed=True,
            staged_dev=1,
            staged_ino=2,
            journal_updated=False,
            deletion_ready=True,
            target_result=CleanupTargetResult(
                subject_type=t.subject_type,
                subject_id=t.subject_id,
                run_id=t.run_id,
                root_relative_path=t.root_relative_path,
                canonical_path=t.canonical_path,
                status=TargetStatus.VISIBLE_REMOVED,
                message="x",
            ),
        )


def test_handle_store_never_evicts_claimed(tmp_path):
    from transcriptx.web.services.run_cleanup import handles as handle_store
    from transcriptx.web.services.run_cleanup.handles import HandleStoreFullError

    handle_store._reset_for_tests()
    svc = _svc(tmp_path)
    _mk_run(svc.outputs_dir, "slug_cap", "20200101_000000_00000001")
    # Fill store with claimed handles
    tokens = []
    for i in range(handle_store._MAX_ENTRIES):
        h, p = svc.preview_cleanup(CleanupMode.DELETE_ALL, f"s{i}")
        tokens.append(h)
        handle_store.claim_handle(h, f"s{i}")
    with pytest.raises(HandleStoreFullError):
        svc.preview_cleanup(CleanupMode.DELETE_ALL, "overflow")
    # Claimed handles still peekable
    state, _, _ = handle_store.peek_handle(tokens[0], "s0")
    assert state == "in_progress"
    handle_store._reset_for_tests()


def test_fault_after_rename_is_partial(tmp_path):
    from transcriptx.web.services.run_cleanup import faults

    svc = _svc(tmp_path)
    run = _mk_run(svc.outputs_dir, "slug_post", "20200101_000000_00000001")
    handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")

    def boom():
        raise RuntimeError("injected after rename")

    faults.set_fault_hook("after_first_rename", boom)
    try:
        result = svc.execute_cleanup(
            handle,
            CleanupAuthorization(
                acknowledged=True,
                phrase=CONFIRM_DELETE_ALL,
                mode=CleanupMode.DELETE_ALL,
                plan_id=preview.plan_id,
            ),
            "s1",
        )
    finally:
        faults.clear_fault_hooks()
    assert result.status is CleanupStatus.PARTIAL
    assert result.visible_removed_count >= 1
    assert not run.exists()
    # Gate released
    gate = try_run_tree_mutation_gate(state_dir=svc.state_dir)
    assert gate is not None
    gate.release()


def test_output_service_public_writers_acquire_or_require_lease():
    """Inventory: public run-tree writers must acquire lock or require lease."""
    import inspect

    from transcriptx.core.output import group_output_service as gos
    from transcriptx.core.output import group_row_writer as grw
    from transcriptx.core.output import output_service as mod

    for name in (
        "save_data",
        "save_text",
        "save_view_html",
        "save_chart",
        "save_summary",
        "record_file",
    ):
        method = getattr(mod.OutputService, name)
        body = inspect.getsource(method)
        assert (
            "_run_write" in body
            or "per_run_lock" in body
            or "assert_lease_for_run" in body
        ), f"{name} must acquire per_run_lock or require RunWriterLease"

    for name in (
        "save_summary",
        "save_session_table",
        "save_combined_json",
        "save_combined_csv",
        "write_group_run_metadata",
        "write_group_manifest",
    ):
        method = getattr(gos.GroupOutputService, name)
        body = inspect.getsource(method)
        assert (
            "per_run_lock" in body or "run_tree_mutation_gate" in body
        ), f"GroupOutputService.{name} must acquire a writer lock"

    assert "per_run_lock" in inspect.getsource(grw.write_row_outputs)


def test_crash_before_post_rename_journal_is_recoverable(tmp_path):
    """Rename succeeds but staged journal write never happens → pending + retry."""
    from transcriptx.web.services.run_cleanup import faults
    from transcriptx.web.services.run_cleanup import journal as cleanup_journal

    svc = _svc(tmp_path)
    run = _mk_run(svc.outputs_dir, "slug_crash", "20200101_000000_00000001")
    handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")

    def boom():
        raise RuntimeError("crash before post-rename journal")

    faults.set_fault_hook("before_post_rename_journal", boom)
    try:
        partial = svc.execute_cleanup(
            handle,
            CleanupAuthorization(
                True, CONFIRM_DELETE_ALL, CleanupMode.DELETE_ALL, preview.plan_id
            ),
            "s1",
        )
    finally:
        faults.clear_fault_hooks()

    assert partial.status is CleanupStatus.PARTIAL
    assert partial.operation_id
    assert not run.exists()
    data = cleanup_journal.load_operation(
        svc.state_dir,
        partial.operation_id,
        expected_policy_version=4,
        expected_schema_version=3,
    )
    assert data is not None
    states = {t["state"] for t in data["targets"]}
    assert states & {
        "staging_started",
        "staged_journal_incomplete",
        "staged_identity_unverified",
    }
    pending = svc.list_pending_staging()
    assert any(p["operation_id"] == partial.operation_id for p in pending)

    retry = svc.retry_interrupted_staging(partial.operation_id)
    assert retry.status in {CleanupStatus.SUCCESS, CleanupStatus.PARTIAL}
    assert retry.physically_deleted_count >= 1
    staging = svc.outputs_dir / ".cleanup_staging" / partial.operation_id
    assert not staging.exists() or not any(staging.iterdir())


def test_physical_delete_verified_reconciles_when_staging_gone(tmp_path):
    """Journal at physical_delete_verified with absent staging → retry succeeds."""
    from transcriptx.web.services.run_cleanup import journal as cleanup_journal
    from transcriptx.web.services.run_cleanup.models import (
        CLEANUP_POLICY_VERSION,
        JOURNAL_SCHEMA_VERSION,
        CleanupPlan,
        CleanupTarget,
        EntryClassification,
        RootIdentity,
        SubjectType,
    )

    svc = _svc(tmp_path)
    run = _mk_run(svc.outputs_dir, "slug_pdv", "20200101_000000_00000001")
    st = run.lstat()
    from transcriptx.web.services.run_cleanup.fingerprint import (
        compute_tree_fingerprint,
    )

    fp, _, _ = compute_tree_fingerprint(run, st.st_dev)
    target = CleanupTarget(
        subject_type=SubjectType.transcript,
        subject_id="slug_pdv",
        run_id="20200101_000000_00000001",
        root_relative_path="slug_pdv/20200101_000000_00000001",
        canonical_path=str(run.resolve()),
        mtime_ns=st.st_mtime_ns,
        filesystem_dev=st.st_dev,
        filesystem_ino=st.st_ino,
        size_estimate_bytes=1,
        file_count=1,
        tree_fingerprint=fp,
        safety_status=EntryClassification.eligible,
    )
    root_st = svc.outputs_dir.lstat()
    plan = CleanupPlan(
        plan_id="p",
        mode=CleanupMode.DELETE_ALL,
        policy_version=CLEANUP_POLICY_VERSION,
        created_at_iso="t",
        roots=(
            RootIdentity(
                kind=SubjectType.transcript,
                configured_path=str(svc.outputs_dir),
                canonical_path=str(svc.outputs_dir.resolve()),
                dev=root_st.st_dev,
                ino=root_st.st_ino,
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
    oid = cleanup_journal.new_operation_id()
    staging = cleanup_journal.intended_staging_path(svc.outputs_dir, oid, target)
    cleanup_journal.write_operation(
        svc.state_dir,
        operation_id=oid,
        plan=plan,
        staging_destinations={target.canonical_path: str(staging)},
    )
    # Simulate rename + verified delete without physical_deleted journal write
    staging.parent.mkdir(parents=True, exist_ok=True)
    run.rename(staging)
    cleanup_journal.update_target_state(
        svc.state_dir,
        oid,
        canonical_path=target.canonical_path,
        state="physical_delete_verified",
        staging_path=str(staging),
        staged_dev=st.st_dev,
        staged_ino=st.st_ino,
    )
    # Delete staging tree out-of-band (crash after rmdir, before journal)
    import shutil

    shutil.rmtree(staging)

    retry = svc.retry_interrupted_staging(oid)
    assert retry.status is CleanupStatus.SUCCESS
    data = cleanup_journal.load_operation(
        svc.state_dir,
        oid,
        expected_policy_version=CLEANUP_POLICY_VERSION,
        expected_schema_version=JOURNAL_SCHEMA_VERSION,
    )
    assert data is not None
    assert data["targets"][0]["state"] == "physical_deleted"


def test_physical_delete_verified_retry_after_partial_descendant_removal(tmp_path):
    """Interrupted mid-rmtree leaves verified + changed fingerprint; retry must finish."""
    from transcriptx.web.services.run_cleanup import journal as cleanup_journal
    from transcriptx.web.services.run_cleanup.models import (
        CLEANUP_POLICY_VERSION,
        JOURNAL_SCHEMA_VERSION,
        CleanupPlan,
        CleanupTarget,
        EntryClassification,
        RootIdentity,
        SubjectType,
    )
    from transcriptx.web.services.run_cleanup.fingerprint import (
        compute_tree_fingerprint,
    )

    svc = _svc(tmp_path)
    run = _mk_run(svc.outputs_dir, "slug_partial_rm", "20200101_000000_00000001")
    (run / "nested").mkdir()
    (run / "nested" / "deep.txt").write_text("nested", encoding="utf-8")
    (run / "keep.txt").write_text("keep", encoding="utf-8")
    st = run.lstat()
    fp, _, _ = compute_tree_fingerprint(run, st.st_dev)
    target = CleanupTarget(
        subject_type=SubjectType.transcript,
        subject_id="slug_partial_rm",
        run_id="20200101_000000_00000001",
        root_relative_path="slug_partial_rm/20200101_000000_00000001",
        canonical_path=str(run.resolve()),
        mtime_ns=st.st_mtime_ns,
        filesystem_dev=st.st_dev,
        filesystem_ino=st.st_ino,
        size_estimate_bytes=1,
        file_count=3,
        tree_fingerprint=fp,
        safety_status=EntryClassification.eligible,
    )
    root_st = svc.outputs_dir.lstat()
    plan = CleanupPlan(
        plan_id="p",
        mode=CleanupMode.DELETE_ALL,
        policy_version=CLEANUP_POLICY_VERSION,
        created_at_iso="t",
        roots=(
            RootIdentity(
                kind=SubjectType.transcript,
                configured_path=str(svc.outputs_dir),
                canonical_path=str(svc.outputs_dir.resolve()),
                dev=root_st.st_dev,
                ino=root_st.st_ino,
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
    oid = cleanup_journal.new_operation_id()
    staging = cleanup_journal.intended_staging_path(svc.outputs_dir, oid, target)
    cleanup_journal.write_operation(
        svc.state_dir,
        operation_id=oid,
        plan=plan,
        staging_destinations={target.canonical_path: str(staging)},
    )
    staging.parent.mkdir(parents=True, exist_ok=True)
    run.rename(staging)
    # Simulate crash after some descendants were removed: fingerprint no longer matches.
    import shutil

    shutil.rmtree(staging / "nested")
    (staging / "artifact.txt").unlink()
    assert staging.exists()
    assert not run.exists()
    staged_st = staging.lstat()
    cleanup_journal.update_target_state(
        svc.state_dir,
        oid,
        canonical_path=target.canonical_path,
        state="physical_delete_verified",
        staging_path=str(staging),
        staged_dev=staged_st.st_dev,
        staged_ino=staged_st.st_ino,
    )

    retry = svc.retry_interrupted_staging(oid)
    assert retry.status is CleanupStatus.SUCCESS
    assert retry.physically_deleted_count >= 1
    assert not staging.exists()
    assert not run.exists()
    data = cleanup_journal.load_operation(
        svc.state_dir,
        oid,
        expected_policy_version=CLEANUP_POLICY_VERSION,
        expected_schema_version=JOURNAL_SCHEMA_VERSION,
    )
    assert data is not None
    assert data["targets"][0]["state"] == "physical_deleted"


def test_physical_delete_partial_reconciles_when_both_absent(tmp_path):
    """Final rmdir ok but parent fsync failed: staging gone → retry marks deleted."""
    from transcriptx.web.services.run_cleanup import journal as cleanup_journal
    from transcriptx.web.services.run_cleanup.models import (
        CLEANUP_POLICY_VERSION,
        JOURNAL_SCHEMA_VERSION,
        CleanupPlan,
        CleanupTarget,
        EntryClassification,
        RootIdentity,
        SubjectType,
    )
    from transcriptx.web.services.run_cleanup.fingerprint import (
        compute_tree_fingerprint,
    )

    svc = _svc(tmp_path)
    run = _mk_run(svc.outputs_dir, "slug_pdp", "20200101_000000_00000001")
    st = run.lstat()
    fp, _, _ = compute_tree_fingerprint(run, st.st_dev)
    target = CleanupTarget(
        subject_type=SubjectType.transcript,
        subject_id="slug_pdp",
        run_id="20200101_000000_00000001",
        root_relative_path="slug_pdp/20200101_000000_00000001",
        canonical_path=str(run.resolve()),
        mtime_ns=st.st_mtime_ns,
        filesystem_dev=st.st_dev,
        filesystem_ino=st.st_ino,
        size_estimate_bytes=1,
        file_count=1,
        tree_fingerprint=fp,
        safety_status=EntryClassification.eligible,
    )
    root_st = svc.outputs_dir.lstat()
    plan = CleanupPlan(
        plan_id="p",
        mode=CleanupMode.DELETE_ALL,
        policy_version=CLEANUP_POLICY_VERSION,
        created_at_iso="t",
        roots=(
            RootIdentity(
                kind=SubjectType.transcript,
                configured_path=str(svc.outputs_dir),
                canonical_path=str(svc.outputs_dir.resolve()),
                dev=root_st.st_dev,
                ino=root_st.st_ino,
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
    oid = cleanup_journal.new_operation_id()
    staging = cleanup_journal.intended_staging_path(svc.outputs_dir, oid, target)
    cleanup_journal.write_operation(
        svc.state_dir,
        operation_id=oid,
        plan=plan,
        staging_destinations={target.canonical_path: str(staging)},
    )
    staging.parent.mkdir(parents=True, exist_ok=True)
    run.rename(staging)
    cleanup_journal.update_target_state(
        svc.state_dir,
        oid,
        canonical_path=target.canonical_path,
        state="physical_delete_partial",
        staging_path=str(staging),
        staged_dev=st.st_dev,
        staged_ino=st.st_ino,
        extra={"fingerprint_invalidated": True},
    )
    import shutil

    shutil.rmtree(staging)
    assert not staging.exists() and not run.exists()

    retry = svc.retry_interrupted_staging(oid)
    assert retry.status is CleanupStatus.SUCCESS
    data = cleanup_journal.load_operation(
        svc.state_dir,
        oid,
        expected_policy_version=CLEANUP_POLICY_VERSION,
        expected_schema_version=JOURNAL_SCHEMA_VERSION,
    )
    assert data is not None
    assert data["targets"][0]["state"] == "physical_deleted"


def test_physical_delete_verified_does_not_reconcile_when_source_present(tmp_path):
    """Staging absent alone must not record success if the source path exists."""
    from transcriptx.web.services.run_cleanup import journal as cleanup_journal
    from transcriptx.web.services.run_cleanup.models import (
        CLEANUP_POLICY_VERSION,
        JOURNAL_SCHEMA_VERSION,
        CleanupPlan,
        CleanupTarget,
        EntryClassification,
        RootIdentity,
        SubjectType,
    )
    from transcriptx.web.services.run_cleanup.fingerprint import (
        compute_tree_fingerprint,
    )

    svc = _svc(tmp_path)
    run = _mk_run(svc.outputs_dir, "slug_src", "20200101_000000_00000001")
    st = run.lstat()
    fp, _, _ = compute_tree_fingerprint(run, st.st_dev)
    target = CleanupTarget(
        subject_type=SubjectType.transcript,
        subject_id="slug_src",
        run_id="20200101_000000_00000001",
        root_relative_path="slug_src/20200101_000000_00000001",
        canonical_path=str(run.resolve()),
        mtime_ns=st.st_mtime_ns,
        filesystem_dev=st.st_dev,
        filesystem_ino=st.st_ino,
        size_estimate_bytes=1,
        file_count=1,
        tree_fingerprint=fp,
        safety_status=EntryClassification.eligible,
    )
    root_st = svc.outputs_dir.lstat()
    plan = CleanupPlan(
        plan_id="p",
        mode=CleanupMode.DELETE_ALL,
        policy_version=CLEANUP_POLICY_VERSION,
        created_at_iso="t",
        roots=(
            RootIdentity(
                kind=SubjectType.transcript,
                configured_path=str(svc.outputs_dir),
                canonical_path=str(svc.outputs_dir.resolve()),
                dev=root_st.st_dev,
                ino=root_st.st_ino,
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
    oid = cleanup_journal.new_operation_id()
    staging = cleanup_journal.intended_staging_path(svc.outputs_dir, oid, target)
    cleanup_journal.write_operation(
        svc.state_dir,
        operation_id=oid,
        plan=plan,
        staging_destinations={target.canonical_path: str(staging)},
    )
    # Journal claims verified deletion, but source still exists and staging does not.
    cleanup_journal.update_target_state(
        svc.state_dir,
        oid,
        canonical_path=target.canonical_path,
        state="physical_delete_verified",
        staging_path=str(staging),
        staged_dev=st.st_dev,
        staged_ino=st.st_ino,
    )
    assert run.exists() and not staging.exists()

    retry = svc.retry_interrupted_staging(oid)
    data = cleanup_journal.load_operation(
        svc.state_dir,
        oid,
        expected_policy_version=CLEANUP_POLICY_VERSION,
        expected_schema_version=JOURNAL_SCHEMA_VERSION,
    )
    assert data is not None
    assert data["targets"][0]["state"] != "physical_deleted"
    assert run.exists()
    assert retry.status is not CleanupStatus.SUCCESS


def test_multi_target_retry_not_success_with_remnant(tmp_path):
    """One deleted target + one still-pending remnant → PARTIAL, never SUCCESS."""
    from transcriptx.web.services.run_cleanup import journal as cleanup_journal
    from transcriptx.web.services.run_cleanup.models import (
        CLEANUP_POLICY_VERSION,
        JOURNAL_SCHEMA_VERSION,
    )

    svc = _svc(tmp_path)
    _mk_run(svc.outputs_dir, "slug_a", "20200101_000000_00000001")
    _mk_run(svc.outputs_dir, "slug_b", "20200101_000000_00000002")
    handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")
    from transcriptx.web.services.run_cleanup import faults

    def boom():
        raise RuntimeError("stop after first rename")

    faults.set_fault_hook("after_first_rename", boom)
    try:
        partial = svc.execute_cleanup(
            handle,
            CleanupAuthorization(
                True, CONFIRM_DELETE_ALL, CleanupMode.DELETE_ALL, preview.plan_id
            ),
            "s1",
        )
    finally:
        faults.clear_fault_hooks()

    assert partial.status is CleanupStatus.PARTIAL
    data = cleanup_journal.load_operation(
        svc.state_dir,
        partial.operation_id,
        expected_policy_version=CLEANUP_POLICY_VERSION,
        expected_schema_version=JOURNAL_SCHEMA_VERSION,
    )
    assert data is not None
    # Leave second target as staging_started/planned remnant; recover first only
    states = [t["state"] for t in data["targets"]]
    assert any(s != "physical_deleted" for s in states)

    # Manually mark one target physical_deleted while leaving another pending
    targets = data["targets"]
    if len(targets) >= 2:
        cleanup_journal.update_target_state(
            svc.state_dir,
            partial.operation_id,
            canonical_path=targets[0]["canonical_path"],
            state="physical_deleted",
        )
        # Ensure second remains mid-flight
        if targets[1]["state"] == "physical_deleted":
            cleanup_journal.update_target_state(
                svc.state_dir,
                partial.operation_id,
                canonical_path=targets[1]["canonical_path"],
                state="staging_started",
                staging_path=targets[1].get("staging_path"),
            )
        status = RunCleanupService._status_from_journal_targets(
            list(
                cleanup_journal.load_operation(
                    svc.state_dir,
                    partial.operation_id,
                    expected_policy_version=CLEANUP_POLICY_VERSION,
                    expected_schema_version=JOURNAL_SCHEMA_VERSION,
                )["targets"]
            )
        )
        assert status is CleanupStatus.PARTIAL


def test_journal_create_failure_after_claim_stores_result(tmp_path, monkeypatch):
    """Journal create raising after claim must not leave handle in_progress bare."""
    from transcriptx.web.services.run_cleanup import handles as handle_store
    from transcriptx.web.services.run_cleanup import journal as cleanup_journal

    svc = _svc(tmp_path)
    _mk_run(svc.outputs_dir, "slug_j", "20200101_000000_00000001")
    handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")

    def boom(*_a, **_k):
        raise cleanup_journal.JournalDurabilityError("injected journal create failure")

    monkeypatch.setattr(cleanup_journal, "write_operation", boom)
    result = svc.execute_cleanup(
        handle,
        CleanupAuthorization(
            True, CONFIRM_DELETE_ALL, CleanupMode.DELETE_ALL, preview.plan_id
        ),
        "s1",
    )
    assert result.status is CleanupStatus.FAILED_BEFORE_MUTATION
    state, _, prior = handle_store.peek_handle(handle, "s1")
    assert state == "completed"
    assert prior is not None
    assert prior.status is CleanupStatus.FAILED_BEFORE_MUTATION


def test_rename_refuses_identity_change_under_subject(tmp_path):
    """Descriptor-anchored rename refuses when run identity changes before renameat."""
    from transcriptx.web.services.run_cleanup.models import (
        CleanupTarget,
        EntryClassification,
        RootIdentity,
        SubjectType,
    )
    from transcriptx.web.services.run_cleanup.staging import (
        StagingUnsafeError,
        ensure_secure_staging_directory,
        rename_into_staging,
    )

    svc = _svc(tmp_path)
    run = _mk_run(svc.outputs_dir, "slug_id", "20200101_000000_00000001")
    st = run.lstat()
    target = CleanupTarget(
        subject_type=SubjectType.transcript,
        subject_id="slug_id",
        run_id="20200101_000000_00000001",
        root_relative_path="slug_id/20200101_000000_00000001",
        canonical_path=str(run.resolve()),
        mtime_ns=st.st_mtime_ns,
        filesystem_dev=st.st_dev,
        filesystem_ino=st.st_ino,
        size_estimate_bytes=1,
        file_count=1,
        tree_fingerprint="0" * 64,
        safety_status=EntryClassification.eligible,
    )
    root_st = svc.outputs_dir.lstat()
    root = RootIdentity(
        kind=SubjectType.transcript,
        configured_path=str(svc.outputs_dir),
        canonical_path=str(svc.outputs_dir.resolve()),
        dev=root_st.st_dev,
        ino=root_st.st_ino,
        is_symlink=False,
    )
    layout = ensure_secure_staging_directory(
        svc.outputs_dir, "1_abcdefabcdef", target, root
    )
    try:
        with pytest.raises(StagingUnsafeError, match="identity changed"):
            rename_into_staging(
                run,
                layout,
                expected_dev=st.st_dev,
                expected_ino=st.st_ino + 999999,
                root_relative_path=target.root_relative_path,
            )
    finally:
        layout.close()


def test_parent_fsync_failure_is_partial(tmp_path, monkeypatch):
    from transcriptx.web.services.run_cleanup import physical_delete as pd
    from transcriptx.web.services.run_cleanup.physical_delete import (
        PhysicalDeletePartialError,
        _fsync_parent,
    )

    path = tmp_path / "staged" / "leaf"
    path.mkdir(parents=True)

    def boom(fd):
        raise OSError(5, "EIO injected")

    monkeypatch.setattr(pd.os, "fsync", boom)
    with pytest.raises(PhysicalDeletePartialError, match="parent fsync failed"):
        _fsync_parent(path)


def test_parent_fsync_ebadf_is_tolerated(tmp_path, monkeypatch):
    import errno

    from transcriptx.web.services.run_cleanup import physical_delete as pd
    from transcriptx.web.services.run_cleanup.physical_delete import _fsync_parent

    path = tmp_path / "staged" / "leaf"
    path.mkdir(parents=True)

    def boom(fd):
        raise OSError(errno.EBADF, "Bad file descriptor")

    monkeypatch.setattr(pd.os, "fsync", boom)
    _fsync_parent(path)  # does not raise
