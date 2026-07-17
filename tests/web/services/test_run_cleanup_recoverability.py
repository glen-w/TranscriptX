"""Deep recoverability tests for cleanup crash windows and journal state machine."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest

from transcriptx.web.services.run_cleanup import deletion_phase
from transcriptx.web.services.run_cleanup import (
    CONFIRM_DELETE_ALL,
    CleanupAuthorization,
    CleanupMode,
    CleanupStatus,
    RunCleanupService,
    TargetStatus,
)
from transcriptx.web.services.run_cleanup import faults
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
from transcriptx.web.services.run_cleanup.physical_delete import (
    PhysicalDeletePartialError,
    safe_rmtree_verified,
    verify_staged_tree,
)
from transcriptx.web.services.run_cleanup.staging import (
    StagingUnsafeError,
    ensure_secure_staging_directory,
    rename_into_staging,
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


def _mk_run(root: Path, slug: str, run_id: str, content: str = "x") -> Path:
    run = root / slug / run_id
    run.mkdir(parents=True, exist_ok=True)
    (run / "artifact.txt").write_text(content, encoding="utf-8")
    return run


def _auth(plan_id: str) -> CleanupAuthorization:
    return CleanupAuthorization(
        acknowledged=True,
        phrase=CONFIRM_DELETE_ALL,
        mode=CleanupMode.DELETE_ALL,
        plan_id=plan_id,
    )


def _load(svc: RunCleanupService, operation_id: str) -> dict[str, Any]:
    data = cleanup_journal.load_operation(
        svc.state_dir,
        operation_id,
        expected_policy_version=CLEANUP_POLICY_VERSION,
        expected_schema_version=JOURNAL_SCHEMA_VERSION,
    )
    assert data is not None
    return data


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


def _write_single_target_journal(
    svc: RunCleanupService,
    target: CleanupTarget,
    *,
    state: str,
    staging_path: Path | None = None,
    staged_dev: int | None = None,
    staged_ino: int | None = None,
) -> str:
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
    dest = staging_path or cleanup_journal.intended_staging_path(
        svc.outputs_dir, oid, target
    )
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
            staged_dev=staged_dev,
            staged_ino=staged_ino,
        )
        cleanup_journal.update_operation_status(svc.state_dir, oid, "PARTIAL")
    return oid


# ---------------------------------------------------------------------------
# Exact crash-window state assertions
# ---------------------------------------------------------------------------


class TestStagingStartedCrashWindow:
    def test_rename_failure_after_staging_started_persists_state(
        self, tmp_path, monkeypatch
    ):
        svc = _svc(tmp_path)
        run = _mk_run(svc.outputs_dir, "slug_ss", "20200101_000000_00000001")
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")

        def boom(*_a, **_k):
            raise StagingUnsafeError("injected rename refusal")

        monkeypatch.setattr(
            "transcriptx.web.services.run_cleanup.staging_phase.rename_into_staging",
            boom,
        )
        result = svc.execute_cleanup(handle, _auth(preview.plan_id), "s1")
        assert result.status in {
            CleanupStatus.PARTIAL,
            CleanupStatus.FAILED_BEFORE_MUTATION,
        }
        assert run.exists()
        assert result.operation_id
        data = _load(svc, result.operation_id)
        assert data["targets"][0]["state"] in {"staging_started", "staging_failed"}
        # staging_started must be pending if rename never moved the tree
        if data["targets"][0]["state"] == "staging_started":
            pending = svc.list_pending_staging()
            assert any(p["operation_id"] == result.operation_id for p in pending)

    def test_exact_staged_journal_incomplete_on_post_rename_crash(self, tmp_path):
        svc = _svc(tmp_path)
        run = _mk_run(svc.outputs_dir, "slug_sji", "20200101_000000_00000001")
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")

        def boom():
            raise RuntimeError("crash before staged journal")

        faults.set_fault_hook("before_post_rename_journal", boom)
        try:
            result = svc.execute_cleanup(handle, _auth(preview.plan_id), "s1")
        finally:
            faults.clear_fault_hooks()

        assert result.status is CleanupStatus.PARTIAL
        assert not run.exists()
        data = _load(svc, result.operation_id)
        assert data["targets"][0]["state"] == "staged_journal_incomplete"
        assert any(
            t.status is TargetStatus.STAGED_JOURNAL_INCOMPLETE for t in result.targets
        )
        retry = svc.retry_interrupted_staging(result.operation_id)
        assert retry.physically_deleted_count >= 1
        assert retry.status in {CleanupStatus.SUCCESS, CleanupStatus.PARTIAL}

    def test_staged_write_fsync_failed_marks_journal_incomplete(
        self, tmp_path, monkeypatch
    ):
        svc = _svc(tmp_path)
        run = _mk_run(svc.outputs_dir, "slug_fsync", "20200101_000000_00000001")
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")

        real_update = cleanup_journal.update_target_state

        def flaky_update(state_dir, operation_id, *, canonical_path, state, **kwargs):
            result = real_update(
                state_dir,
                operation_id,
                canonical_path=canonical_path,
                state=state,
                **kwargs,
            )
            if state == "staged":
                return cleanup_journal.DirFsyncResult(
                    cleanup_journal.DirFsyncOutcome.FAILED, "injected staged fsync fail"
                )
            return result

        monkeypatch.setattr(cleanup_journal, "update_target_state", flaky_update)
        # service imports journal as module alias — patch where used
        monkeypatch.setattr(
            "transcriptx.web.services.run_cleanup.journal.update_target_state",
            flaky_update,
        )
        result = svc.execute_cleanup(handle, _auth(preview.plan_id), "s1")
        assert result.status is CleanupStatus.PARTIAL
        assert not run.exists()
        assert any(
            t.status is TargetStatus.STAGED_JOURNAL_INCOMPLETE for t in result.targets
        )
        data = _load(svc, result.operation_id)
        assert data["targets"][0]["state"] == "staged_journal_incomplete"

    def test_before_staged_lstat_fault_persists_identity_unverified(self, tmp_path):
        svc = _svc(tmp_path)
        run = _mk_run(svc.outputs_dir, "slug_lstat", "20200101_000000_00000001")
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")

        def boom():
            raise RuntimeError("crash before staged lstat")

        faults.set_fault_hook("before_staged_lstat", boom)
        try:
            result = svc.execute_cleanup(handle, _auth(preview.plan_id), "s1")
        finally:
            faults.clear_fault_hooks()

        assert result.status is CleanupStatus.PARTIAL
        assert not run.exists()
        data = _load(svc, result.operation_id)
        assert data["targets"][0]["state"] == "staged_identity_unverified"
        assert any(
            t.status is TargetStatus.STAGED_IDENTITY_UNVERIFIED for t in result.targets
        )
        pending = svc.list_pending_staging()
        assert any(p["state"] == "staged_identity_unverified" for p in pending)


class TestPhysicalDeleteDurability:
    def test_physical_deleted_fsync_failed_demotes_success(self, tmp_path, monkeypatch):
        svc = _svc(tmp_path)
        _mk_run(svc.outputs_dir, "slug_pdf", "20200101_000000_00000001")
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")

        real_update = cleanup_journal.update_target_state

        def flaky_update(state_dir, operation_id, *, canonical_path, state, **kwargs):
            result = real_update(
                state_dir,
                operation_id,
                canonical_path=canonical_path,
                state=state,
                **kwargs,
            )
            if state == "physical_deleted":
                return cleanup_journal.DirFsyncResult(
                    cleanup_journal.DirFsyncOutcome.FAILED,
                    "injected physical_deleted fsync fail",
                )
            return result

        monkeypatch.setattr(
            "transcriptx.web.services.run_cleanup.journal.update_target_state",
            flaky_update,
        )
        result = svc.execute_cleanup(handle, _auth(preview.plan_id), "s1")
        assert result.status is CleanupStatus.PARTIAL
        assert any("journal durability failed" in e for e in result.errors)
        assert result.physically_deleted_count >= 1

    def test_terminal_journal_fsync_failed_demotes_success(self, tmp_path, monkeypatch):
        svc = _svc(tmp_path)
        _mk_run(svc.outputs_dir, "slug_term", "20200101_000000_00000001")
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")

        real_update = cleanup_journal.update_operation_status

        def flaky_status(state_dir, operation_id, status, **extra):
            result = real_update(state_dir, operation_id, status, **extra)
            if status == CleanupStatus.SUCCESS.value:
                return cleanup_journal.DirFsyncResult(
                    cleanup_journal.DirFsyncOutcome.FAILED,
                    "injected terminal fsync fail",
                )
            return result

        monkeypatch.setattr(
            "transcriptx.web.services.run_cleanup.journal.update_operation_status",
            flaky_status,
        )
        result = svc.execute_cleanup(handle, _auth(preview.plan_id), "s1")
        assert result.status is CleanupStatus.PARTIAL
        assert any("terminal journal durability failed" in e for e in result.errors)

    def test_during_delete_fault_leaves_verified_or_partial(self, tmp_path):
        svc = _svc(tmp_path)
        run = _mk_run(svc.outputs_dir, "slug_dd", "20200101_000000_00000001")
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")

        def boom():
            raise OSError("injected during delete")

        faults.set_fault_hook("during_delete", boom)
        try:
            result = svc.execute_cleanup(handle, _auth(preview.plan_id), "s1")
        finally:
            faults.clear_fault_hooks()

        assert result.status is CleanupStatus.PARTIAL
        assert result.operation_id
        data = _load(svc, result.operation_id)
        state = data["targets"][0]["state"]
        assert state in {
            "physical_delete_verified",
            "physical_delete_failed",
            "physical_delete_partial",
            "staged",
        }
        # Remnant still recoverable
        pending = svc.list_pending_staging()
        assert any(p["operation_id"] == result.operation_id for p in pending)
        assert not run.exists() or state in {"staged", "physical_delete_verified"}


class TestRetryReconcileMatrix:
    def test_staging_present_source_absent_recovers_and_deletes(self, tmp_path):
        svc = _svc(tmp_path)
        run = _mk_run(svc.outputs_dir, "slug_rec", "20200101_000000_00000001")
        target = _target_from_run(
            run, subject_id="slug_rec", run_id="20200101_000000_00000001"
        )
        oid = _write_single_target_journal(svc, target, state="staging_started")
        staging = cleanup_journal.intended_staging_path(svc.outputs_dir, oid, target)
        staging.parent.mkdir(parents=True, exist_ok=True)
        run.rename(staging)
        assert staging.exists() and not run.exists()

        retry = svc.retry_interrupted_staging(oid)
        assert retry.status is CleanupStatus.SUCCESS
        assert retry.physically_deleted_count >= 1
        assert not staging.exists()
        data = _load(svc, oid)
        assert data["targets"][0]["state"] == "physical_deleted"

    def test_both_present_refuses_delete(self, tmp_path):
        svc = _svc(tmp_path)
        run = _mk_run(svc.outputs_dir, "slug_both", "20200101_000000_00000001")
        target = _target_from_run(
            run, subject_id="slug_both", run_id="20200101_000000_00000001"
        )
        oid = _write_single_target_journal(svc, target, state="staging_started")
        staging = cleanup_journal.intended_staging_path(svc.outputs_dir, oid, target)
        staging.parent.mkdir(parents=True, exist_ok=True)
        # Copy so both exist (identity won't match staging, but reconcile refuses both-present first)
        shutil.copytree(run, staging)

        retry = svc.retry_interrupted_staging(oid)
        assert retry.status is CleanupStatus.PARTIAL
        assert any(
            t.status is TargetStatus.PHYSICAL_DELETE_REFUSED for t in retry.targets
        )
        assert any("both present" in t.message for t in retry.targets)
        assert run.exists() and staging.exists()

    def test_both_absent_marks_external_disappeared(self, tmp_path):
        svc = _svc(tmp_path)
        run = _mk_run(svc.outputs_dir, "slug_gone", "20200101_000000_00000001")
        target = _target_from_run(
            run, subject_id="slug_gone", run_id="20200101_000000_00000001"
        )
        oid = _write_single_target_journal(svc, target, state="staging_started")
        shutil.rmtree(run)

        retry = svc.retry_interrupted_staging(oid)
        # Phase B2: external_disappeared is not a SUCCESS fact.
        assert retry.status is CleanupStatus.PARTIAL
        assert any(t.status is TargetStatus.EXTERNAL_DISAPPEARED for t in retry.targets)
        data = _load(svc, oid)
        assert data["targets"][0]["state"] == "external_disappeared"

    def test_source_present_staging_absent_skips(self, tmp_path):
        svc = _svc(tmp_path)
        run = _mk_run(svc.outputs_dir, "slug_skip", "20200101_000000_00000001")
        target = _target_from_run(
            run, subject_id="slug_skip", run_id="20200101_000000_00000001"
        )
        oid = _write_single_target_journal(svc, target, state="planned")
        cleanup_journal.update_operation_status(svc.state_dir, oid, "PARTIAL")

        retry = svc.retry_interrupted_staging(oid)
        assert any(t.status is TargetStatus.SKIPPED for t in retry.targets)
        assert run.exists()
        data = _load(svc, oid)
        assert data["targets"][0]["state"] == "planned"
        # All planned → FAILED_BEFORE_MUTATION after reconcile
        assert retry.status is CleanupStatus.FAILED_BEFORE_MUTATION

    def test_staged_identity_mismatch_refuses(self, tmp_path):
        svc = _svc(tmp_path)
        run = _mk_run(svc.outputs_dir, "slug_idmis", "20200101_000000_00000001")
        target = _target_from_run(
            run, subject_id="slug_idmis", run_id="20200101_000000_00000001"
        )
        oid = _write_single_target_journal(svc, target, state="staging_started")
        staging = cleanup_journal.intended_staging_path(svc.outputs_dir, oid, target)
        staging.parent.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(run)
        # Fresh tree at staging path → different inode than journaled identity.
        staging.mkdir(parents=True)
        (staging / "artifact.txt").write_text("replacement", encoding="utf-8")

        retry = svc.retry_interrupted_staging(oid)
        assert retry.status is CleanupStatus.PARTIAL
        assert any(
            t.status is TargetStatus.PHYSICAL_DELETE_REFUSED for t in retry.targets
        )
        assert any("identity does not match" in t.message for t in retry.targets)
        assert staging.exists()

    def test_missing_staged_dev_ino_recovers_via_lstat(self, tmp_path):
        svc = _svc(tmp_path)
        run = _mk_run(svc.outputs_dir, "slug_lstat", "20200101_000000_00000001")
        target = _target_from_run(
            run, subject_id="slug_lstat", run_id="20200101_000000_00000001"
        )
        oid = _write_single_target_journal(svc, target, state="staging_started")
        staging = cleanup_journal.intended_staging_path(svc.outputs_dir, oid, target)
        staging.parent.mkdir(parents=True, exist_ok=True)
        run.rename(staging)
        # Journal has no staged_dev/ino; reconcile must lstat and match identity.
        retry = svc.retry_interrupted_staging(oid)
        assert retry.status is CleanupStatus.SUCCESS
        assert not staging.exists()
        data = _load(svc, oid)
        assert data["targets"][0]["state"] == "physical_deleted"


class TestTerminalReconstruction:
    def test_success_terminal_rebuilds_targets(self, tmp_path):
        from transcriptx.web.services.run_cleanup import recovery as recovery_mod

        svc = _svc(tmp_path)
        run = _mk_run(svc.outputs_dir, "slug_term", "20200101_000000_00000001")
        target = _target_from_run(
            run, subject_id="slug_term", run_id="20200101_000000_00000001"
        )
        oid = _write_single_target_journal(svc, target, state="physical_deleted")
        cleanup_journal.update_operation_status(svc.state_dir, oid, "SUCCESS")
        data = _load(svc, oid)
        result = recovery_mod._synthesize_terminal_result(
            operation_id=oid,
            plan_id="plan",
            mode=CleanupMode.DELETE_ALL,
            data=data,
        )
        assert result.status is CleanupStatus.ALREADY_EXECUTED
        assert len(result.targets) == 1
        assert result.targets[0].status is TargetStatus.PHYSICAL_DELETED
        assert result.targets[0].filesystem_dev == target.filesystem_dev
        assert result.physically_deleted_count == 1

    def test_malformed_target_row_warns_without_fabricating_ids(self, tmp_path):
        from transcriptx.web.services.run_cleanup import recovery as recovery_mod

        result = recovery_mod._synthesize_terminal_result(
            operation_id="1_abcdef012345",
            plan_id="plan",
            mode=CleanupMode.DELETE_ALL,
            data={
                "status": "SUCCESS",
                "targets": [
                    {
                        "subject_type": "transcript",
                        "subject_id": "s",
                        "run_id": "r",
                        "canonical_path": "/x",
                        "state": "physical_deleted",
                        "filesystem_dev": 0,
                        "filesystem_ino": 0,
                    }
                ],
            },
        )
        assert result.status is CleanupStatus.ALREADY_EXECUTED
        assert result.targets == ()
        assert any("could not be reconstructed" in w for w in result.warnings)

    def test_op_status_vs_target_vector_conflict_warns(self, tmp_path):
        from transcriptx.web.services.run_cleanup import recovery as recovery_mod

        svc = _svc(tmp_path)
        run = _mk_run(svc.outputs_dir, "slug_conf", "20200101_000000_00000001")
        target = _target_from_run(
            run, subject_id="slug_conf", run_id="20200101_000000_00000001"
        )
        oid = _write_single_target_journal(svc, target, state="physical_deleted")
        cleanup_journal.update_operation_status(svc.state_dir, oid, "PARTIAL")
        data = _load(svc, oid)
        result = recovery_mod._synthesize_terminal_result(
            operation_id=oid,
            plan_id="plan",
            mode=CleanupMode.DELETE_ALL,
            data=data,
        )
        assert result.status is CleanupStatus.ALREADY_EXECUTED
        assert any("differs from" in w for w in result.warnings)


class TestMultiTargetRemnant:
    def test_retry_with_one_deleted_one_remnant_is_partial(self, tmp_path):
        svc = _svc(tmp_path)
        run_a = _mk_run(svc.outputs_dir, "slug_a", "20200101_000000_00000001")
        run_b = _mk_run(svc.outputs_dir, "slug_b", "20200101_000000_00000002")
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")

        def boom():
            raise RuntimeError("stop after first rename")

        faults.set_fault_hook("after_first_rename", boom)
        try:
            partial = svc.execute_cleanup(handle, _auth(preview.plan_id), "s1")
        finally:
            faults.clear_fault_hooks()

        assert partial.status is CleanupStatus.PARTIAL
        data = _load(svc, partial.operation_id)
        # Force first target complete; leave second mid-flight with staged remnant if present
        targets = sorted(data["targets"], key=lambda t: t["canonical_path"])
        cleanup_journal.update_target_state(
            svc.state_dir,
            partial.operation_id,
            canonical_path=targets[0]["canonical_path"],
            state="physical_deleted",
        )
        if targets[1]["state"] == "physical_deleted":
            cleanup_journal.update_target_state(
                svc.state_dir,
                partial.operation_id,
                canonical_path=targets[1]["canonical_path"],
                state="staging_started",
                staging_path=targets[1].get("staging_path"),
            )
        # Ensure remnant tree for second if source was renamed
        staging_b = Path(targets[1].get("staging_path") or "")
        if (
            staging_b
            and not staging_b.exists()
            and not Path(targets[1]["canonical_path"]).exists()
        ):
            # recreate empty remnant so retry has something to refuse or recover
            staging_b.mkdir(parents=True, exist_ok=True)
            (staging_b / "artifact.txt").write_text("remnant", encoding="utf-8")

        retry = svc.retry_interrupted_staging(partial.operation_id)
        assert retry.status is CleanupStatus.PARTIAL
        _ = svc.list_pending_staging()
        # Either still pending or fully cleaned; if SUCCESS forbidden when remnant state mid-flight
        reloaded = _load(svc, partial.operation_id)
        states = {t["state"] for t in reloaded["targets"]}
        if states - {
            "physical_deleted",
            "external_disappeared",
            "locked_skip",
            "staging_failed",
        }:
            assert retry.status is CleanupStatus.PARTIAL
        assert not (
            run_a.exists() and run_b.exists() and retry.status is CleanupStatus.SUCCESS
        )


class TestRefusedFailedJournalWrites:
    def test_unrecognised_staging_path_writes_refused(self, tmp_path):
        svc = _svc(tmp_path)
        run = _mk_run(svc.outputs_dir, "slug_ref", "20200101_000000_00000001")
        target = _target_from_run(
            run, subject_id="slug_ref", run_id="20200101_000000_00000001"
        )
        oid = _write_single_target_journal(svc, target, state="staged")
        fake_staging = svc.outputs_dir / "not_staging" / "fake"
        fake_staging.mkdir(parents=True)
        (fake_staging / "x.txt").write_text("x", encoding="utf-8")

        tr = deletion_phase.physical_delete_one(svc, target, fake_staging, oid)
        assert tr.status is TargetStatus.PHYSICAL_DELETE_REFUSED
        data = _load(svc, oid)
        assert data["targets"][0]["state"] == "physical_delete_refused"
        pending = svc.list_pending_staging()
        assert any(p["state"] == "physical_delete_refused" for p in pending)

    def test_verified_journal_durability_failure_writes_failed(
        self, tmp_path, monkeypatch
    ):
        svc = _svc(tmp_path)
        run = _mk_run(svc.outputs_dir, "slug_vfail", "20200101_000000_00000001")
        target = _target_from_run(
            run, subject_id="slug_vfail", run_id="20200101_000000_00000001"
        )
        oid = _write_single_target_journal(svc, target, state="staged")
        staging = cleanup_journal.intended_staging_path(svc.outputs_dir, oid, target)
        staging.parent.mkdir(parents=True, exist_ok=True)
        run.rename(staging)
        st = staging.lstat()
        cleanup_journal.update_target_state(
            svc.state_dir,
            oid,
            canonical_path=target.canonical_path,
            state="staged",
            staging_path=str(staging),
            staged_dev=st.st_dev,
            staged_ino=st.st_ino,
        )

        real_update = cleanup_journal.update_target_state

        def flaky_update(state_dir, operation_id, *, canonical_path, state, **kwargs):
            if state == "physical_delete_verified":
                raise cleanup_journal.JournalDurabilityError("injected verified fail")
            return real_update(
                state_dir,
                operation_id,
                canonical_path=canonical_path,
                state=state,
                **kwargs,
            )

        monkeypatch.setattr(
            "transcriptx.web.services.run_cleanup.journal.update_target_state",
            flaky_update,
        )
        tr = deletion_phase.physical_delete_one(
            svc,
            target,
            staging,
            oid,
            staged_dev=st.st_dev,
            staged_ino=st.st_ino,
        )
        assert tr.status is TargetStatus.PHYSICAL_DELETE_FAILED
        # Best-effort may have written physical_delete_failed via persist_target_state
        # which also goes through the patched function — ensure staging still present
        assert staging.exists()


class TestClaimRetryDurability:
    def test_claim_fsync_failed_blocks_retry(self, tmp_path, monkeypatch):
        svc = _svc(tmp_path)
        run = _mk_run(svc.outputs_dir, "slug_claim", "20200101_000000_00000001")
        target = _target_from_run(
            run, subject_id="slug_claim", run_id="20200101_000000_00000001"
        )
        oid = _write_single_target_journal(svc, target, state="staged")
        staging = cleanup_journal.intended_staging_path(svc.outputs_dir, oid, target)
        staging.parent.mkdir(parents=True, exist_ok=True)
        run.rename(staging)
        st = staging.lstat()
        cleanup_journal.update_target_state(
            svc.state_dir,
            oid,
            canonical_path=target.canonical_path,
            state="staged",
            staging_path=str(staging),
            staged_dev=st.st_dev,
            staged_ino=st.st_ino,
        )

        def failed_claim(state_dir, operation_id):
            return cleanup_journal.DirFsyncResult(
                cleanup_journal.DirFsyncOutcome.FAILED, "injected claim fsync fail"
            )

        monkeypatch.setattr(
            "transcriptx.web.services.run_cleanup.journal.claim_retry_ownership",
            failed_claim,
        )
        result = svc.retry_interrupted_staging(oid)
        assert result.status is CleanupStatus.BLOCKED
        assert any("retry claim journal durability failed" in e for e in result.errors)
        assert staging.exists()


class TestTerminalRetry:
    @pytest.mark.parametrize("status", ["BLOCKED", "STALE_PLAN", "SUCCESS"])
    def test_terminal_statuses_retry_as_already_executed(self, tmp_path, status):
        svc = _svc(tmp_path)
        oid = "1_abcdefabcdef"
        ops = svc.state_dir / "cleanup" / "operations"
        ops.mkdir(parents=True)
        (ops / f"{oid}.json").write_text(
            f'{{"journal_schema_version": {JOURNAL_SCHEMA_VERSION},'
            f' "cleanup_policy_version": {CLEANUP_POLICY_VERSION},'
            f' "operation_id": "{oid}", "plan_id": "p", "mode": "DELETE_ALL",'
            f' "policy_version": {CLEANUP_POLICY_VERSION}, "created_at": 1,'
            f' "roots": [], "targets": [], "status": "{status}"}}\n',
            encoding="utf-8",
        )
        result = svc.retry_interrupted_staging(oid)
        assert result.status is CleanupStatus.ALREADY_EXECUTED
        assert any("already terminal" in w.lower() for w in result.warnings)


class TestDescriptorRename:
    def test_subject_entry_identity_mismatch_refuses(self, tmp_path):
        svc = _svc(tmp_path)
        run = _mk_run(svc.outputs_dir, "slug_swap", "20200101_000000_00000001")
        target = _target_from_run(
            run, subject_id="slug_swap", run_id="20200101_000000_00000001"
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
            # Replace run directory with a new inode under the same name
            shutil.rmtree(run)
            run.mkdir(parents=True)
            (run / "artifact.txt").write_text("replaced", encoding="utf-8")
            with pytest.raises(StagingUnsafeError, match="identity changed"):
                rename_into_staging(
                    run,
                    layout,
                    expected_dev=target.filesystem_dev,
                    expected_ino=target.filesystem_ino,
                    root_relative_path=target.root_relative_path,
                )
            assert run.exists()
        finally:
            layout.close()


class TestParentFsyncIntegration:
    def test_safe_rmtree_parent_fsync_failure_is_partial(self, tmp_path, monkeypatch):
        svc = _svc(tmp_path)
        run = _mk_run(svc.outputs_dir, "slug_pfs", "20200101_000000_00000001")
        target = _target_from_run(
            run, subject_id="slug_pfs", run_id="20200101_000000_00000001"
        )
        oid = _write_single_target_journal(svc, target, state="staged")
        staging = cleanup_journal.intended_staging_path(svc.outputs_dir, oid, target)
        staging.parent.mkdir(parents=True, exist_ok=True)
        run.rename(staging)
        st = staging.lstat()
        proof = verify_staged_tree(
            staging_path=staging,
            planned_filesystem_dev=target.filesystem_dev,
            planned_filesystem_ino=target.filesystem_ino,
            planned_fingerprint=target.tree_fingerprint,
            staged_dev=st.st_dev,
            staged_ino=st.st_ino,
            operation_id=oid,
            canonical_source_path=target.canonical_path,
            subject_type=target.subject_type.value,
            subject_id=target.subject_id,
            run_id=target.run_id,
        )

        import transcriptx.web.services.run_cleanup.physical_delete as pd

        def boom(fd):
            raise OSError(5, "EIO injected parent fsync")

        monkeypatch.setattr(pd.os, "fsync", boom)
        with pytest.raises(PhysicalDeletePartialError, match="parent fsync failed"):
            safe_rmtree_verified(proof)


class TestFaultPointSweep:
    @pytest.mark.parametrize(
        "point",
        [
            "before_physical_verify",
            "after_physical_verify",
            "before_terminal_journal",
            "after_staged_lstat",
        ],
    )
    def test_fault_points_do_not_leave_handle_in_progress(self, tmp_path, point):
        from transcriptx.web.services.run_cleanup import handles as handle_store

        svc = _svc(tmp_path)
        _mk_run(svc.outputs_dir, "slug_fp", "20200101_000000_00000001")
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")

        def boom():
            raise RuntimeError(f"injected at {point}")

        faults.set_fault_hook(point, boom)
        try:
            result = svc.execute_cleanup(handle, _auth(preview.plan_id), "s1")
        finally:
            faults.clear_fault_hooks()

        assert result.status in {
            CleanupStatus.PARTIAL,
            CleanupStatus.FAILED_BEFORE_MUTATION,
            CleanupStatus.BLOCKED,
            CleanupStatus.SUCCESS,
        }
        state, _, prior = handle_store.peek_handle(handle, "s1")
        assert state == "completed"
        assert prior is not None
