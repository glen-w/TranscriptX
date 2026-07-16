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


def test_status_from_journal_targets_vector():
    from transcriptx.web.services.run_cleanup.models import CleanupStatus
    from transcriptx.web.services.run_cleanup.service import RunCleanupService

    assert (
        RunCleanupService._status_from_journal_targets(
            [{"state": "physical_deleted"}, {"state": "physical_deleted"}]
        )
        is CleanupStatus.SUCCESS
    )
    assert (
        RunCleanupService._status_from_journal_targets(
            [{"state": "physical_deleted"}, {"state": "staging_started"}]
        )
        is CleanupStatus.PARTIAL
    )
    assert (
        RunCleanupService._status_from_journal_targets(
            [{"state": "planned"}, {"state": "planned"}]
        )
        is CleanupStatus.FAILED_BEFORE_MUTATION
    )
    assert (
        RunCleanupService._status_from_journal_targets(
            [{"state": "physical_deleted"}, {"state": "locked_skip"}]
        )
        is CleanupStatus.SUCCESS
    )
    assert (
        RunCleanupService._status_from_journal_targets(
            [{"state": "physical_delete_verified"}]
        )
        is CleanupStatus.PARTIAL
    )
