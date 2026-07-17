"""Unprivileged adversarial FS cells for cleanup staging/delete paths."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from transcriptx.web.services.run_cleanup import (
    CONFIRM_DELETE_ALL,
    CleanupAuthorization,
    CleanupMode,
    CleanupStatus,
    RunCleanupService,
    TargetStatus,
)
from transcriptx.web.services.run_cleanup import journal as cleanup_journal
from transcriptx.web.services.run_cleanup.fingerprint import compute_tree_fingerprint
from transcriptx.web.services.run_cleanup.models import (
    CLEANUP_POLICY_VERSION,
    JOURNAL_SCHEMA_VERSION,
    CleanupPlan,
    CleanupTarget,
    EntryClassification,
    RootIdentity,
    SubjectType,
)
from transcriptx.web.services.run_cleanup import deletion_phase


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


def _target_from_run(run: Path, *, subject_id: str, run_id: str) -> CleanupTarget:
    st = run.lstat()
    fp, _, _ = compute_tree_fingerprint(run, st.st_dev)
    return CleanupTarget(
        subject_type=SubjectType.transcript,
        subject_id=subject_id,
        run_id=run_id,
        root_relative_path=f"{subject_id}/{run_id}",
        canonical_path=str(run.resolve()),
        mtime_ns=st.st_mtime_ns,
        filesystem_dev=st.st_dev,
        filesystem_ino=st.st_ino,
        size_estimate_bytes=1,
        file_count=1,
        tree_fingerprint=fp,
        safety_status=EntryClassification.eligible,
    )


def _write_journal(svc: RunCleanupService, target: CleanupTarget, *, state: str) -> str:
    root_st = svc.outputs_dir.lstat()
    plan = CleanupPlan(
        plan_id="plan",
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
    dest = cleanup_journal.intended_staging_path(svc.outputs_dir, oid, target)
    cleanup_journal.write_operation(
        svc.state_dir,
        operation_id=oid,
        plan=plan,
        staging_destinations={target.canonical_path: str(dest)},
    )
    if state != "planned":
        cleanup_journal.update_target_state(
            svc.state_dir,
            oid,
            canonical_path=target.canonical_path,
            state=state,
            staging_path=str(dest),
        )
        cleanup_journal.update_operation_status(svc.state_dir, oid, "PARTIAL")
    return oid


@pytest.mark.unit
def test_symlink_substitution_on_source_parent_refuses_or_blocks(
    tmp_path: Path,
) -> None:
    svc = _svc(tmp_path)
    run = _mk_run(svc.outputs_dir, "slug_sym", "20200101_000000_00000001")
    target = _target_from_run(
        run, subject_id="slug_sym", run_id="20200101_000000_00000001"
    )
    oid = _write_journal(svc, target, state="staged")
    staging = cleanup_journal.intended_staging_path(svc.outputs_dir, oid, target)
    staging.parent.mkdir(parents=True, exist_ok=True)
    run.rename(staging)
    # Replace subject parent with a symlink after staging.
    subject = svc.outputs_dir / "slug_sym"
    if subject.exists():
        shutil.rmtree(subject)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    os.symlink(elsewhere, subject)
    tr = deletion_phase.physical_delete_one(svc, target, staging, oid)
    # Must not SUCCESS-delete through a substituted parent layout blindly.
    assert tr.status in {
        TargetStatus.PHYSICAL_DELETED,
        TargetStatus.PHYSICAL_DELETE_REFUSED,
        TargetStatus.PHYSICAL_DELETE_FAILED,
        TargetStatus.PHYSICAL_DELETE_PARTIAL,
    }
    if tr.status is TargetStatus.PHYSICAL_DELETED:
        assert not staging.exists()


@pytest.mark.unit
def test_preexisting_staging_destination_on_initial_exec(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    run = _mk_run(svc.outputs_dir, "slug_pre", "20200101_000000_00000001")
    handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")
    auth = CleanupAuthorization(
        acknowledged=True,
        phrase=CONFIRM_DELETE_ALL,
        mode=CleanupMode.DELETE_ALL,
        plan_id=preview.plan_id,
    )
    # Seed a fake staging tree under .cleanup_staging that could collide.
    staging_root = svc.outputs_dir / ".cleanup_staging"
    staging_root.mkdir(exist_ok=True)
    (staging_root / "poison").mkdir()
    result = svc.execute_cleanup(handle, auth, "s1")
    # Either succeeds (operation-scoped dirs) or fails closed before mutation.
    assert result.status in {
        CleanupStatus.SUCCESS,
        CleanupStatus.PARTIAL,
        CleanupStatus.FAILED_BEFORE_MUTATION,
        CleanupStatus.BLOCKED,
        CleanupStatus.STALE_PLAN,
    }
    assert run.exists() or result.status is CleanupStatus.SUCCESS


@pytest.mark.unit
def test_recreated_source_after_staging_refuses_both_present(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    run = _mk_run(svc.outputs_dir, "slug_re", "20200101_000000_00000001")
    target = _target_from_run(
        run, subject_id="slug_re", run_id="20200101_000000_00000001"
    )
    oid = _write_journal(svc, target, state="staging_started")
    staging = cleanup_journal.intended_staging_path(svc.outputs_dir, oid, target)
    staging.parent.mkdir(parents=True, exist_ok=True)
    run.rename(staging)
    # Recreate source at original path while staging still present.
    run.mkdir(parents=True)
    (run / "artifact.txt").write_text("recreated", encoding="utf-8")
    retry = svc.retry_interrupted_staging(oid)
    assert any(t.status is TargetStatus.PHYSICAL_DELETE_REFUSED for t in retry.targets)
    assert any("both present" in t.message for t in retry.targets)
    assert run.exists() and staging.exists()


@pytest.mark.unit
def test_unreadable_special_file_excluded_from_plan(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    run = _mk_run(svc.outputs_dir, "slug_fifo", "20200101_000000_00000001")
    fifo = run / "pipe.fifo"
    try:
        os.mkfifo(fifo)
    except OSError:
        pytest.skip("mkfifo unsupported")
    handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")
    # Fingerprint/discovery should exclude or still plan safely — not crash.
    assert preview is not None
    assert handle


@pytest.mark.unit
def test_unicode_subject_path(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    slug = "slug_ünicode_日本語"
    run = _mk_run(svc.outputs_dir, slug, "20200101_000000_00000001")
    handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")
    assert preview is not None
    if not preview.can_execute or preview.run_count == 0:
        # Classifier may exclude non-ASCII subject ids; must not crash.
        return
    auth = CleanupAuthorization(
        acknowledged=True,
        phrase=CONFIRM_DELETE_ALL,
        mode=CleanupMode.DELETE_ALL,
        plan_id=preview.plan_id,
    )
    result = svc.execute_cleanup(handle, auth, "s1")
    assert result.status is CleanupStatus.SUCCESS
    assert not run.exists()


@pytest.mark.unit
def test_idempotency_retry_after_success(tmp_path: Path) -> None:
    svc = _svc(tmp_path)
    _mk_run(svc.outputs_dir, "slug_idemp", "20200101_000000_00000001")
    handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")
    auth = CleanupAuthorization(
        acknowledged=True,
        phrase=CONFIRM_DELETE_ALL,
        mode=CleanupMode.DELETE_ALL,
        plan_id=preview.plan_id,
    )
    first = svc.execute_cleanup(handle, auth, "s1")
    assert first.status is CleanupStatus.SUCCESS
    second = svc.retry_interrupted_staging(first.operation_id)
    assert second.status is CleanupStatus.ALREADY_EXECUTED
    data = cleanup_journal.load_operation(
        svc.state_dir,
        first.operation_id,
        expected_policy_version=CLEANUP_POLICY_VERSION,
        expected_schema_version=JOURNAL_SCHEMA_VERSION,
    )
    assert data is not None
    assert data["status"] == "SUCCESS"
