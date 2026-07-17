"""Journal operation_id and structural staging recognition tests."""

from __future__ import annotations

import pytest

from transcriptx.web.services.run_cleanup import journal
from transcriptx.web.services.run_cleanup.models import (
    CLEANUP_POLICY_VERSION,
    JOURNAL_SCHEMA_VERSION,
)


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "abc",
        "../x",
        "1_nothexzzzzzz",
        "123_abcd",  # too short hex
        "123_gggggggggggg",
        "123_abcdefabcdef/extra",
        "123_abcdefabcdef..",
    ],
)
def test_reject_malformed_operation_ids(bad):
    with pytest.raises(ValueError):
        journal.validate_operation_id(bad)


def test_accept_valid_operation_id():
    oid = journal.new_operation_id()
    assert journal.validate_operation_id(oid) == oid


def test_fake_staging_not_recognised(tmp_path):
    outputs = tmp_path / "outputs"
    groups = outputs / "groups"
    state = tmp_path / "state"
    outputs.mkdir()
    groups.mkdir()
    state.mkdir()
    fake = outputs / ".cleanup_staging" / "bogus" / "run"
    fake.mkdir(parents=True)
    assert not journal.is_journal_recognised_staging_path(
        state,
        fake,
        operation_id="1_abcdefabcdef",
        subject_type="transcript",
        subject_id="x",
        run_id="y",
        canonical_path="/nope",
        outputs_dir=outputs,
        group_outputs_dir=groups,
        expected_policy_version=CLEANUP_POLICY_VERSION,
        expected_schema_version=JOURNAL_SCHEMA_VERSION,
    )


def test_load_typed_missing(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    result = journal.load_operation_typed(
        state,
        "1_abcdefabcdef",
        expected_policy_version=CLEANUP_POLICY_VERSION,
        expected_schema_version=JOURNAL_SCHEMA_VERSION,
    )
    assert result.kind is journal.JournalLoadKind.MISSING


def test_load_typed_incompatible_schema(tmp_path):
    state = tmp_path / "state"
    ops = state / "cleanup" / "operations"
    ops.mkdir(parents=True)
    oid = "1_abcdefabcdef"
    path = ops / f"{oid}.json"
    path.write_text(
        '{"journal_schema_version": 2, "cleanup_policy_version": 3,'
        f' "operation_id": "{oid}", "plan_id": "p", "mode": "DELETE_ALL",'
        ' "policy_version": 3, "created_at": 1, "roots": [], "targets": [],'
        ' "status": "journaled"}\n',
        encoding="utf-8",
    )
    result = journal.load_operation_typed(
        state,
        oid,
        expected_policy_version=CLEANUP_POLICY_VERSION,
        expected_schema_version=JOURNAL_SCHEMA_VERSION,
    )
    assert result.kind is journal.JournalLoadKind.INCOMPATIBLE


def test_claim_rejects_unknown_status(tmp_path):
    state = tmp_path / "state"
    ops = state / "cleanup" / "operations"
    ops.mkdir(parents=True)
    oid = "1_abcdefabcdef"
    path = ops / f"{oid}.json"
    path.write_text(
        f'{{"journal_schema_version": {JOURNAL_SCHEMA_VERSION},'
        f' "cleanup_policy_version": {CLEANUP_POLICY_VERSION},'
        f' "operation_id": "{oid}", "plan_id": "p", "mode": "DELETE_ALL",'
        f' "policy_version": {CLEANUP_POLICY_VERSION}, "created_at": 1,'
        ' "roots": [], "targets": [], "status": "weird_unknown"}\n',
        encoding="utf-8",
    )
    with pytest.raises(journal.JournalClaimError):
        journal.claim_retry_ownership(state, oid)


@pytest.mark.parametrize("status", ["BLOCKED", "STALE_PLAN"])
def test_blocked_and_stale_plan_are_terminal(tmp_path, status):
    state = tmp_path / "state"
    ops = state / "cleanup" / "operations"
    ops.mkdir(parents=True)
    oid = "1_abcdefabcdef"
    path = ops / f"{oid}.json"
    path.write_text(
        f'{{"journal_schema_version": {JOURNAL_SCHEMA_VERSION},'
        f' "cleanup_policy_version": {CLEANUP_POLICY_VERSION},'
        f' "operation_id": "{oid}", "plan_id": "p", "mode": "DELETE_ALL",'
        f' "policy_version": {CLEANUP_POLICY_VERSION}, "created_at": 1,'
        f' "roots": [], "targets": [], "status": "{status}"}}\n',
        encoding="utf-8",
    )
    result = journal.load_operation_typed(
        state,
        oid,
        expected_policy_version=CLEANUP_POLICY_VERSION,
        expected_schema_version=JOURNAL_SCHEMA_VERSION,
    )
    assert result.kind is journal.JournalLoadKind.TERMINAL


def test_pending_includes_staging_started(tmp_path):
    state = tmp_path / "state"
    ops = state / "cleanup" / "operations"
    ops.mkdir(parents=True)
    oid = "1_abcdefabcdef"
    path = ops / f"{oid}.json"
    path.write_text(
        f'{{"journal_schema_version": {JOURNAL_SCHEMA_VERSION},'
        f' "cleanup_policy_version": {CLEANUP_POLICY_VERSION},'
        f' "operation_id": "{oid}", "plan_id": "p", "mode": "DELETE_ALL",'
        f' "policy_version": {CLEANUP_POLICY_VERSION}, "created_at": 1,'
        ' "roots": [], "targets": [{'
        ' "subject_type": "transcript", "subject_id": "s", "run_id": "r",'
        ' "root_relative_path": "s/r", "canonical_path": "/tmp/s/r",'
        f' "tree_fingerprint": "{"0" * 64}", "filesystem_dev": 1,'
        ' "filesystem_ino": 2, "staging_path": "/tmp/stage",'
        ' "staged_dev": null, "staged_ino": null, "state": "staging_started"'
        '}], "status": "PARTIAL"}\n',
        encoding="utf-8",
    )
    pending = journal.list_pending_staging(state)
    assert len(pending) == 1
    assert pending[0]["state"] == "staging_started"
    assert pending[0]["operation_id"] == oid


@pytest.mark.parametrize(
    "target_state",
    [
        "planned",
        "staging_started",
        "staged",
        "staged_journal_incomplete",
        "staged_identity_unverified",
        "physical_delete_verified",
        "physical_delete_refused",
        "physical_delete_failed",
        "physical_delete_partial",
    ],
)
def test_list_pending_includes_recoverable_states(tmp_path, target_state):
    state = tmp_path / "state"
    ops = state / "cleanup" / "operations"
    ops.mkdir(parents=True)
    oid = "1_abcdefabcdef"
    path = ops / f"{oid}.json"
    path.write_text(
        f'{{"journal_schema_version": {JOURNAL_SCHEMA_VERSION},'
        f' "cleanup_policy_version": {CLEANUP_POLICY_VERSION},'
        f' "operation_id": "{oid}", "plan_id": "p", "mode": "DELETE_ALL",'
        f' "policy_version": {CLEANUP_POLICY_VERSION}, "created_at": 1,'
        ' "roots": [], "targets": [{'
        ' "subject_type": "transcript", "subject_id": "s", "run_id": "r",'
        ' "root_relative_path": "s/r", "canonical_path": "/tmp/s/r",'
        f' "tree_fingerprint": "{"0" * 64}", "filesystem_dev": 1,'
        ' "filesystem_ino": 2, "staging_path": "/tmp/stage",'
        f' "staged_dev": null, "staged_ino": null, "state": "{target_state}"'
        '}], "status": "PARTIAL"}\n',
        encoding="utf-8",
    )
    pending = journal.list_pending_staging(state)
    assert len(pending) == 1
    assert pending[0]["state"] == target_state


@pytest.mark.parametrize("op_status", ["SUCCESS", "BLOCKED", "STALE_PLAN", "NOOP"])
def test_list_pending_excludes_terminal_operations(tmp_path, op_status):
    state = tmp_path / "state"
    ops = state / "cleanup" / "operations"
    ops.mkdir(parents=True)
    oid = "1_abcdefabcdef"
    path = ops / f"{oid}.json"
    path.write_text(
        f'{{"journal_schema_version": {JOURNAL_SCHEMA_VERSION},'
        f' "cleanup_policy_version": {CLEANUP_POLICY_VERSION},'
        f' "operation_id": "{oid}", "plan_id": "p", "mode": "DELETE_ALL",'
        f' "policy_version": {CLEANUP_POLICY_VERSION}, "created_at": 1,'
        ' "roots": [], "targets": [{'
        ' "subject_type": "transcript", "subject_id": "s", "run_id": "r",'
        ' "root_relative_path": "s/r", "canonical_path": "/tmp/s/r",'
        f' "tree_fingerprint": "{"0" * 64}", "filesystem_dev": 1,'
        ' "filesystem_ino": 2, "staging_path": "/tmp/stage",'
        ' "staged_dev": null, "staged_ino": null, "state": "staged"'
        f'}}], "status": "{op_status}"}}\n',
        encoding="utf-8",
    )
    assert journal.list_pending_staging(state) == []


def test_fsync_dir_treats_ebadf_as_unsupported(tmp_path, monkeypatch):
    """Docker Desktop bind mounts often return EBADF for directory fsync."""
    import errno
    import os

    real_open = os.open

    def open_then_bad_fsync(path, flags, *a, **k):
        return real_open(path, flags, *a, **k)

    def boom(fd):
        raise OSError(errno.EBADF, "Bad file descriptor")

    monkeypatch.setattr(journal.os, "open", open_then_bad_fsync)
    monkeypatch.setattr(journal.os, "fsync", boom)
    result = journal.fsync_dir(tmp_path)
    assert result.outcome is journal.DirFsyncOutcome.UNSUPPORTED
    assert "Bad file descriptor" in result.message


def test_write_operation_tolerates_unsupported_dir_fsync(tmp_path, monkeypatch):
    from transcriptx.web.services.run_cleanup.models import (
        CleanupMode,
        CleanupPlan,
        CleanupTarget,
        EntryClassification,
        RootIdentity,
        SubjectType,
    )

    monkeypatch.setattr(
        journal,
        "fsync_dir",
        lambda _d: journal.DirFsyncResult(
            journal.DirFsyncOutcome.UNSUPPORTED, "[Errno 9] Bad file descriptor"
        ),
    )
    plan = CleanupPlan(
        plan_id="p",
        mode=CleanupMode.DELETE_OLD,
        policy_version=CLEANUP_POLICY_VERSION,
        created_at_iso="t",
        roots=(
            RootIdentity(
                kind=SubjectType.transcript,
                configured_path=str(tmp_path / "out"),
                canonical_path=str(tmp_path / "out"),
                dev=1,
                ino=2,
                is_symlink=False,
            ),
        ),
        candidates=(
            CleanupTarget(
                subject_type=SubjectType.transcript,
                subject_id="s",
                run_id="r",
                root_relative_path="s/r",
                canonical_path=str(tmp_path / "out" / "s" / "r"),
                mtime_ns=1,
                filesystem_dev=1,
                filesystem_ino=3,
                size_estimate_bytes=1,
                file_count=1,
                tree_fingerprint="0" * 64,
                safety_status=EntryClassification.eligible,
            ),
        ),
        retained=(),
        exclusions=(),
        warnings=(),
        blocking_errors=(),
        can_execute=True,
    )
    oid = "1_abcdefabcdef"
    path = journal.write_operation(tmp_path / "state", operation_id=oid, plan=plan)
    assert path.is_file()


def test_status_from_journal_targets_vector():
    from transcriptx.web.services.run_cleanup.models import CleanupStatus
    from transcriptx.web.services.run_cleanup import results as results_mod
    from transcriptx.web.services.run_cleanup.service import RunCleanupService

    assert (
        results_mod.status_from_journal_targets(
            [{"state": "physical_deleted"}, {"state": "physical_deleted"}]
        )
        is CleanupStatus.SUCCESS
    )
    assert (
        results_mod.status_from_journal_targets(
            [{"state": "physical_deleted"}, {"state": "staging_started"}]
        )
        is CleanupStatus.PARTIAL
    )
    assert (
        results_mod.status_from_journal_targets(
            [{"state": "planned"}, {"state": "planned"}]
        )
        is CleanupStatus.FAILED_BEFORE_MUTATION
    )
    assert (
        results_mod.status_from_journal_targets(
            [{"state": "physical_deleted"}, {"state": "locked_skip"}]
        )
        is CleanupStatus.SUCCESS
    )
    assert (
        results_mod.status_from_journal_targets([{"state": "physical_delete_verified"}])
        is CleanupStatus.PARTIAL
    )
    # Private shim still used by journal / release-blocker tests.
    assert RunCleanupService._status_from_journal_targets([]) is CleanupStatus.NOOP
