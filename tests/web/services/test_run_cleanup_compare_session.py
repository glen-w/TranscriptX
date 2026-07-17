"""Execution-compare, session-clear, and identity helper contracts."""

from __future__ import annotations


import pytest

from transcriptx.web.services.run_cleanup.execution_compare import (
    compare_with_lock_skip_masks,
)
from transcriptx.web.services.run_cleanup.identity import (
    TargetIdentity,
    TargetKey,
    ensure_descendant,
    root_relative,
    sorted_identity_dicts,
)
from transcriptx.web.services.run_cleanup.models import (
    CleanupExclusion,
    CleanupMode,
    CleanupPlan,
    CleanupTarget,
    CleanupTargetResult,
    EntryClassification,
    RootIdentity,
    SubjectType,
    TargetStatus,
)
from transcriptx.web.services.run_cleanup.plan_builder import ExecutionSet
from transcriptx.web.services.run_cleanup.session_clear import (
    clear_session_selections_for_removed_runs,
)
from transcriptx.web.state import (
    RUN_ID_KEY,
    SELECTED_RUN_DIR,
    SUBJECT_ID_KEY,
    SUBJECT_TYPE_KEY,
)


def _target(
    subject_id: str,
    run_id: str,
    *,
    fingerprint: str = "a" * 64,
    ino: int = 1,
    subject_type: SubjectType = SubjectType.transcript,
    mtime_ns: int = 1,
) -> CleanupTarget:
    return CleanupTarget(
        subject_type=subject_type,
        subject_id=subject_id,
        run_id=run_id,
        root_relative_path=f"{subject_id}/{run_id}",
        canonical_path=f"/outputs/{subject_id}/{run_id}",
        mtime_ns=mtime_ns,
        filesystem_dev=1,
        filesystem_ino=ino,
        size_estimate_bytes=1,
        file_count=1,
        tree_fingerprint=fingerprint,
        safety_status=EntryClassification.eligible,
    )


def _root() -> RootIdentity:
    return RootIdentity(
        kind=SubjectType.transcript,
        configured_path="/outputs",
        canonical_path="/outputs",
        dev=1,
        ino=10,
        is_symlink=False,
    )


def _plan(
    mode: CleanupMode,
    candidates: tuple[CleanupTarget, ...],
    retained: tuple[CleanupTarget, ...] = (),
    exclusions: tuple[CleanupExclusion, ...] = (),
) -> CleanupPlan:
    return CleanupPlan(
        plan_id="p1",
        mode=mode,
        policy_version=4,
        created_at_iso="2020-01-01T00:00:00+00:00",
        roots=(_root(),),
        candidates=candidates,
        retained=retained,
        exclusions=exclusions,
        warnings=(),
        blocking_errors=(),
        can_execute=True,
    )


def _es(
    mode: CleanupMode,
    *,
    eligible: tuple[CleanupTarget, ...],
    candidates: tuple[CleanupTarget, ...],
    retained: tuple[CleanupTarget, ...] = (),
    exclusions: tuple[CleanupExclusion, ...] = (),
) -> ExecutionSet:
    return ExecutionSet(
        mode=mode,
        roots=(_root(),),
        eligible=eligible,
        candidates=candidates,
        retained=retained,
        exclusions=exclusions,
        policy_version=4,
        classifier_version=1,
        newest_run_policy_version=1,
        can_execute=True,
        blocking_errors=(),
        warnings=(),
    )


def _result(
    t: CleanupTarget,
    status: TargetStatus,
    *,
    filesystem_dev: int | None = None,
    filesystem_ino: int | None = None,
) -> CleanupTargetResult:
    return CleanupTargetResult(
        subject_type=t.subject_type,
        subject_id=t.subject_id,
        run_id=t.run_id,
        root_relative_path=t.root_relative_path,
        canonical_path=t.canonical_path,
        status=status,
        filesystem_dev=filesystem_dev,
        filesystem_ino=filesystem_ino,
    )


class TestExecutionCompare:
    def test_identical_sets_ok(self):
        t = _target("s", "20200101_000000_00000001")
        planned = _plan(CleanupMode.DELETE_ALL, (t,))
        rediscovered = _es(
            CleanupMode.DELETE_ALL,
            eligible=(t,),
            candidates=(t,),
        )
        ok, reason = compare_with_lock_skip_masks(
            planned=planned, rediscovered=rediscovered, lock_results=()
        )
        assert ok is True
        assert reason == ""

    def test_classifier_version_mismatch_is_stale(self):
        t = _target("s", "20200101_000000_00000001")
        planned = _plan(CleanupMode.DELETE_ALL, (t,))
        rediscovered = ExecutionSet(
            mode=CleanupMode.DELETE_ALL,
            roots=(_root(),),
            eligible=(t,),
            candidates=(t,),
            retained=(),
            exclusions=(),
            policy_version=4,
            classifier_version=99,
            newest_run_policy_version=1,
            can_execute=True,
            blocking_errors=(),
            warnings=(),
        )
        ok, reason = compare_with_lock_skip_masks(
            planned=planned, rediscovered=rediscovered, lock_results=()
        )
        assert ok is False
        assert "classifier_version" in reason

    def test_fingerprint_change_is_stale_without_mask(self):
        t1 = _target("s", "20200101_000000_00000001", fingerprint="a" * 64)
        t2 = _target("s", "20200101_000000_00000001", fingerprint="b" * 64)
        planned = _plan(CleanupMode.DELETE_ALL, (t1,))
        rediscovered = _es(
            CleanupMode.DELETE_ALL,
            eligible=(t2,),
            candidates=(t2,),
        )
        ok, reason = compare_with_lock_skip_masks(
            planned=planned, rediscovered=rediscovered, lock_results=()
        )
        assert ok is False
        assert "fingerprint" in reason

    def test_delete_all_locked_skip_masks_fingerprint_only(self):
        t1 = _target("s", "20200101_000000_00000001", fingerprint="a" * 64)
        t2 = _target("s", "20200101_000000_00000001", fingerprint="b" * 64)
        planned = _plan(CleanupMode.DELETE_ALL, (t1,))
        rediscovered = _es(
            CleanupMode.DELETE_ALL,
            eligible=(t2,),
            candidates=(t2,),
        )
        ok, reason = compare_with_lock_skip_masks(
            planned=planned,
            rediscovered=rediscovered,
            lock_results=[_result(t1, TargetStatus.LOCKED_SKIP)],
        )
        assert ok is True
        assert reason == ""

    def test_delete_all_locked_skip_still_requires_core_identity(self):
        t1 = _target("s", "20200101_000000_00000001", ino=1)
        t2 = _target("s", "20200101_000000_00000001", ino=99)
        planned = _plan(CleanupMode.DELETE_ALL, (t1,))
        rediscovered = _es(
            CleanupMode.DELETE_ALL,
            eligible=(t2,),
            candidates=(t2,),
        )
        ok, reason = compare_with_lock_skip_masks(
            planned=planned,
            rediscovered=rediscovered,
            lock_results=[_result(t1, TargetStatus.LOCKED_SKIP)],
        )
        assert ok is False
        assert "core identity" in reason

    def test_delete_old_subject_skip_masks_subject_fingerprints(self):
        older = _target("s", "20200101_000000_00000001", fingerprint="a" * 64, ino=1)
        newer = _target("s", "20200101_000000_00000002", fingerprint="c" * 64, ino=2)
        older2 = _target("s", "20200101_000000_00000001", fingerprint="z" * 64, ino=1)
        newer2 = _target("s", "20200101_000000_00000002", fingerprint="y" * 64, ino=2)
        planned = _plan(CleanupMode.DELETE_OLD, (older,), retained=(newer,))
        rediscovered = _es(
            CleanupMode.DELETE_OLD,
            eligible=(older2, newer2),
            candidates=(older2,),
            retained=(newer2,),
        )
        ok, _ = compare_with_lock_skip_masks(
            planned=planned,
            rediscovered=rediscovered,
            lock_results=[_result(older, TargetStatus.SUBJECT_LOCKED_SKIP)],
        )
        assert ok is True

    def test_membership_change_is_stale(self):
        t1 = _target("s", "20200101_000000_00000001")
        t2 = _target("s", "20200101_000000_00000002", ino=2)
        planned = _plan(CleanupMode.DELETE_ALL, (t1,))
        rediscovered = _es(
            CleanupMode.DELETE_ALL,
            eligible=(t1, t2),
            candidates=(t1, t2),
        )
        ok, reason = compare_with_lock_skip_masks(
            planned=planned, rediscovered=rediscovered, lock_results=()
        )
        assert ok is False
        assert "membership" in reason

    def test_mode_and_exclusion_mismatches(self):
        t = _target("s", "20200101_000000_00000001")
        planned = _plan(CleanupMode.DELETE_ALL, (t,))
        rediscovered = _es(
            CleanupMode.DELETE_OLD,
            eligible=(t,),
            candidates=(),
            retained=(t,),
        )
        ok, reason = compare_with_lock_skip_masks(
            planned=planned, rediscovered=rediscovered, lock_results=()
        )
        assert ok is False
        assert "mode" in reason

        excl = CleanupExclusion(
            path_relative="x",
            classification=EntryClassification.unknown,
            reason="noise",
        )
        planned2 = _plan(CleanupMode.DELETE_ALL, (t,), exclusions=(excl,))
        rediscovered2 = _es(
            CleanupMode.DELETE_ALL,
            eligible=(t,),
            candidates=(t,),
        )
        ok2, reason2 = compare_with_lock_skip_masks(
            planned=planned2, rediscovered=rediscovered2, lock_results=()
        )
        assert ok2 is False
        assert "exclusion" in reason2


class TestSessionClear:
    def test_does_not_clear_for_lock_skips(self):
        session = {
            SUBJECT_TYPE_KEY: "transcript",
            SUBJECT_ID_KEY: "slug_i",
            RUN_ID_KEY: "20200101_000000_00000001",
        }
        skip = CleanupTargetResult(
            subject_type=SubjectType.transcript,
            subject_id="slug_i",
            run_id="20200101_000000_00000001",
            root_relative_path="slug_i/20200101_000000_00000001",
            canonical_path="/tmp/x",
            status=TargetStatus.LOCKED_SKIP,
        )
        assert clear_session_selections_for_removed_runs(session, [skip]) is False
        assert session[RUN_ID_KEY] == "20200101_000000_00000001"

    def test_clears_on_physical_delete_failed_after_visible_removal(self):
        session = {
            SUBJECT_TYPE_KEY: "transcript",
            SUBJECT_ID_KEY: "slug_i",
            RUN_ID_KEY: "20200101_000000_00000001",
            SELECTED_RUN_DIR: "/outputs/slug_i/20200101_000000_00000001",
        }
        failed = CleanupTargetResult(
            subject_type=SubjectType.transcript,
            subject_id="slug_i",
            run_id="20200101_000000_00000001",
            root_relative_path="slug_i/20200101_000000_00000001",
            canonical_path="/outputs/slug_i/20200101_000000_00000001",
            status=TargetStatus.PHYSICAL_DELETE_FAILED,
        )
        assert clear_session_selections_for_removed_runs(session, [failed]) is True
        assert session.get(RUN_ID_KEY) is None
        assert session.get(SELECTED_RUN_DIR) is None

    def test_dev_ino_mismatch_does_not_clear(self):
        session = {
            SUBJECT_TYPE_KEY: "transcript",
            SUBJECT_ID_KEY: "slug_i",
            RUN_ID_KEY: "20200101_000000_00000001",
            "selected_run_dev": 1,
            "selected_run_ino": 2,
        }
        mismatch = CleanupTargetResult(
            subject_type=SubjectType.transcript,
            subject_id="slug_i",
            run_id="20200101_000000_00000001",
            root_relative_path="slug_i/20200101_000000_00000001",
            canonical_path="/tmp/y",
            status=TargetStatus.PHYSICAL_DELETED,
            filesystem_dev=1,
            filesystem_ino=99,
        )
        assert clear_session_selections_for_removed_runs(session, [mismatch]) is False
        assert session[RUN_ID_KEY] == "20200101_000000_00000001"

    def test_path_only_clear_when_identity_keys_absent(self):
        session = {
            SELECTED_RUN_DIR: "/data/outputs/slug_p/20200101_000000_00000001",
        }
        match = CleanupTargetResult(
            subject_type=SubjectType.transcript,
            subject_id="slug_p",
            run_id="20200101_000000_00000001",
            root_relative_path="slug_p/20200101_000000_00000001",
            canonical_path="/other/canonical",
            status=TargetStatus.VISIBLE_REMOVED,
        )
        assert clear_session_selections_for_removed_runs(session, [match]) is True
        assert session[SELECTED_RUN_DIR] is None


class TestIdentityHelpers:
    def test_ensure_descendant_and_root_relative(self, tmp_path):
        root = tmp_path / "root"
        child = root / "a" / "b"
        root.mkdir()
        child.mkdir(parents=True)
        root_c = str(root.resolve())
        child_c = str(child.resolve())
        ensure_descendant(child_c, root_c)
        assert root_relative(child_c, root_c) == "a/b"
        with pytest.raises(ValueError):
            ensure_descendant(str(tmp_path.resolve()), root_c)

    def test_sorted_identity_dicts_deterministic(self):
        k1 = TargetKey(
            root_kind=SubjectType.transcript,
            subject_type=SubjectType.transcript,
            subject_id="b",
            run_id="r1",
            canonical_source_path="/b/r1",
        )
        k2 = TargetKey(
            root_kind=SubjectType.transcript,
            subject_type=SubjectType.transcript,
            subject_id="a",
            run_id="r1",
            canonical_source_path="/a/r1",
        )
        items = [
            TargetIdentity(k1, 1, 2, "f" * 64),
            TargetIdentity(k2, 1, 3, "e" * 64),
        ]
        ordered = sorted_identity_dicts(items)
        assert ordered[0]["subject_id"] == "a"
        assert ordered[1]["subject_id"] == "b"
