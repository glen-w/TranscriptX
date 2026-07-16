"""Physical-delete verification, handle-store, and journal durability edges."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from transcriptx.web.services.run_cleanup import journal
from transcriptx.web.services.run_cleanup.fingerprint import compute_tree_fingerprint
from transcriptx.web.services.run_cleanup.handles import (
    claim_handle,
    create_handle,
    get_plan,
    invalidate_all,
    invalidate_on_policy_change,
    invalidate_on_root_change,
    peek_handle,
    store_result,
)
from transcriptx.web.services.run_cleanup import handles as handle_store
from transcriptx.web.services.run_cleanup.models import (
    CLEANUP_POLICY_VERSION,
    JOURNAL_SCHEMA_VERSION,
    CleanupMode,
    CleanupPlan,
    CleanupResult,
    CleanupStatus,
    CleanupTarget,
    EntryClassification,
    RootIdentity,
    STAGING_DIR_NAME,
    SubjectType,
)
from transcriptx.web.services.run_cleanup.physical_delete import (
    PhysicalDeleteUnsafeError,
    safe_rmtree_verified,
    verify_staged_tree,
)
from transcriptx.web.services.run_cleanup.root_validator import paths_overlap
from transcriptx.web.services.run_cleanup.staging import (
    collision_proof_staging_basename,
    intended_staging_path,
)


def _target(path: Path, *, fingerprint: str, ino: int | None = None) -> CleanupTarget:
    st = path.lstat()
    return CleanupTarget(
        subject_type=SubjectType.transcript,
        subject_id="slug",
        run_id="20200101_000000_00000001",
        root_relative_path="slug/20200101_000000_00000001",
        canonical_path=str(path.resolve()),
        mtime_ns=int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9))),
        filesystem_dev=int(st.st_dev),
        filesystem_ino=int(ino if ino is not None else st.st_ino),
        size_estimate_bytes=1,
        file_count=1,
        tree_fingerprint=fingerprint,
        safety_status=EntryClassification.eligible,
    )


def _minimal_plan(candidates: tuple[CleanupTarget, ...] = ()) -> CleanupPlan:
    root = RootIdentity(
        kind=SubjectType.transcript,
        configured_path="/o",
        canonical_path="/o",
        dev=1,
        ino=1,
        is_symlink=False,
    )
    return CleanupPlan(
        plan_id="plan",
        mode=CleanupMode.DELETE_ALL,
        policy_version=CLEANUP_POLICY_VERSION,
        created_at_iso="2020-01-01T00:00:00+00:00",
        roots=(root,),
        candidates=candidates,
        retained=(),
        exclusions=(),
        warnings=(),
        blocking_errors=(),
        can_execute=True,
    )


class TestVerifyAndDeleteStaged:
    def test_verify_and_delete_nested_staging_tree(self, tmp_path):
        outputs = tmp_path / "outputs"
        outputs.mkdir()
        source = outputs / "slug" / "20200101_000000_00000001"
        source.mkdir(parents=True)
        (source / "a.txt").write_text("hello", encoding="utf-8")
        nested = source / "deep" / "nest"
        nested.mkdir(parents=True)
        (nested / "b.txt").write_text("world", encoding="utf-8")
        st = source.lstat()
        fp, _, _ = compute_tree_fingerprint(source, int(st.st_dev))
        oid = "1_abcdefabcdef"
        target = _target(source, fingerprint=fp)
        staged = intended_staging_path(outputs, oid, target)
        staged.parent.mkdir(parents=True, exist_ok=True)
        os.rename(source, staged)
        proof = verify_staged_tree(
            staging_path=staged,
            planned_filesystem_dev=int(st.st_dev),
            planned_filesystem_ino=int(st.st_ino),
            planned_fingerprint=fp,
            staged_dev=int(st.st_dev),
            staged_ino=int(st.st_ino),
            operation_id=oid,
            canonical_source_path=str(source.resolve()),
            subject_type="transcript",
            subject_id="slug",
            run_id="20200101_000000_00000001",
        )
        safe_rmtree_verified(proof)
        assert not staged.exists()
        assert not source.exists()

    def test_verify_rejects_fingerprint_mismatch(self, tmp_path):
        outputs = tmp_path / "outputs"
        outputs.mkdir()
        source = outputs / "slug" / "20200101_000000_00000001"
        source.mkdir(parents=True)
        (source / "a.txt").write_text("hello", encoding="utf-8")
        st = source.lstat()
        fp, _, _ = compute_tree_fingerprint(source, int(st.st_dev))
        oid = "1_abcdefabcdef"
        target = _target(source, fingerprint=fp)
        staged = intended_staging_path(outputs, oid, target)
        staged.parent.mkdir(parents=True, exist_ok=True)
        os.rename(source, staged)
        (staged / "a.txt").write_text("tampered", encoding="utf-8")
        with pytest.raises(PhysicalDeleteUnsafeError, match="fingerprint"):
            verify_staged_tree(
                staging_path=staged,
                planned_filesystem_dev=int(st.st_dev),
                planned_filesystem_ino=int(st.st_ino),
                planned_fingerprint=fp,
                staged_dev=int(st.st_dev),
                staged_ino=int(st.st_ino),
                operation_id=oid,
                canonical_source_path=str(source.resolve()),
            )

    def test_verify_rejects_when_source_still_present(self, tmp_path):
        outputs = tmp_path / "outputs"
        outputs.mkdir()
        source = outputs / "slug" / "20200101_000000_00000001"
        source.mkdir(parents=True)
        (source / "a.txt").write_text("hello", encoding="utf-8")
        st = source.lstat()
        fp, _, _ = compute_tree_fingerprint(source, int(st.st_dev))
        # Fake a staging path that is a *copy* identity mismatch path:
        # create staging with same content but different inode, then also keep
        # a source with planned ino by not renaming — use hardlink if available
        # or skip when hardlink unsupported.
        oid = "1_abcdefabcdef"
        staging_parent = outputs / STAGING_DIR_NAME / oid
        staging_parent.mkdir(parents=True)
        # Keep source; create a separate staging dir with different ino
        staged = staging_parent / collision_proof_staging_basename(
            _target(source, fingerprint=fp)
        )
        staged.mkdir()
        (staged / "a.txt").write_text("hello", encoding="utf-8")
        staged_st = staged.lstat()
        staged_fp, _, _ = compute_tree_fingerprint(staged, int(staged_st.st_dev))
        with pytest.raises(PhysicalDeleteUnsafeError, match="identity mismatch"):
            verify_staged_tree(
                staging_path=staged,
                planned_filesystem_dev=int(st.st_dev),
                planned_filesystem_ino=int(st.st_ino),
                planned_fingerprint=staged_fp,
                staged_dev=None,
                staged_ino=None,
                operation_id=oid,
                canonical_source_path=str(source.resolve()),
            )


class TestHandleStore:
    def setup_method(self):
        handle_store._reset_for_tests()

    def teardown_method(self):
        handle_store._reset_for_tests()

    def test_create_peek_claim_store_result(self):
        plan = _minimal_plan()
        token = create_handle(plan, "sess")
        state, peeked, prior = peek_handle(token, "sess")
        assert state == "issued"
        assert peeked is not None
        assert prior is None
        claimed, prior2 = claim_handle(token, "sess")
        assert claimed is not None and prior2 is None
        state2, _, _ = peek_handle(token, "sess")
        assert state2 == "in_progress"
        result = CleanupResult(
            operation_id="1_abcdefabcdef",
            plan_id=plan.plan_id,
            mode=CleanupMode.DELETE_ALL,
            status=CleanupStatus.SUCCESS,
            targets=(),
            warnings=(),
            errors=(),
            visible_removed_count=0,
            physically_deleted_count=0,
        )
        store_result(token, "sess", result)
        state3, _, prior3 = peek_handle(token, "sess")
        assert state3 == "completed"
        assert prior3 is not None
        assert prior3.status is CleanupStatus.SUCCESS
        # Wrong session
        assert get_plan(token, "other") is None

    def test_invalidate_on_policy_and_root_change(self):
        plan = _minimal_plan()
        token = create_handle(plan, "sess")
        removed = invalidate_on_policy_change(CLEANUP_POLICY_VERSION + 1)
        assert removed >= 1
        assert peek_handle(token, "sess")[0] == "missing"

        token2 = create_handle(plan, "sess")
        new_roots = (
            RootIdentity(
                kind=SubjectType.transcript,
                configured_path="/changed",
                canonical_path="/changed",
                dev=9,
                ino=9,
                is_symlink=False,
            ),
        )
        removed2 = invalidate_on_root_change(new_roots)
        assert removed2 >= 1
        assert peek_handle(token2, "sess")[0] == "missing"

    def test_evicts_unclaimed_when_full(self):
        # Fill with unclaimed handles then create one more — should evict
        tokens = []
        for i in range(handle_store._MAX_ENTRIES):
            tokens.append(create_handle(_minimal_plan(), f"s{i}"))
        # Should succeed by evicting oldest unclaimed
        overflow = create_handle(_minimal_plan(), "overflow")
        assert overflow
        states = [peek_handle(t, f"s{i}")[0] for i, t in enumerate(tokens)]
        assert "missing" in states
        assert peek_handle(overflow, "overflow")[0] == "issued"

    def test_invalidate_all(self):
        create_handle(_minimal_plan(), "a")
        create_handle(_minimal_plan(), "b")
        invalidate_all()
        assert handle_store._store == {}


class TestJournalDepth:
    def test_write_update_list_pending_and_terminal(self, tmp_path):
        state = tmp_path / "state"
        state.mkdir()
        outputs = tmp_path / "outputs"
        outputs.mkdir()
        run = outputs / "slug" / "20200101_000000_00000001"
        run.mkdir(parents=True)
        (run / "x.txt").write_text("1", encoding="utf-8")
        st = run.lstat()
        fp, _, _ = compute_tree_fingerprint(run, int(st.st_dev))
        target = _target(run, fingerprint=fp)
        plan = _minimal_plan(candidates=(target,))
        oid = journal.new_operation_id()
        staging = journal.intended_staging_path(outputs, oid, target)
        journal.write_operation(
            state,
            operation_id=oid,
            plan=plan,
            staging_destinations={target.canonical_path: str(staging)},
        )
        staging.parent.mkdir(parents=True, exist_ok=True)
        os.rename(run, staging)
        journal.update_target_state(
            state,
            oid,
            canonical_path=target.canonical_path,
            state="interrupted_staging",
            staging_path=str(staging),
            staged_dev=int(st.st_dev),
            staged_ino=int(st.st_ino),
        )
        pending = journal.list_pending_staging(state)
        assert len(pending) == 1
        assert pending[0]["operation_id"] == oid
        assert journal.is_journal_recognised_staging_path(
            state,
            staging,
            operation_id=oid,
            subject_type="transcript",
            subject_id="slug",
            run_id="20200101_000000_00000001",
            canonical_path=target.canonical_path,
            outputs_dir=outputs,
            group_outputs_dir=outputs / "groups",
            expected_policy_version=CLEANUP_POLICY_VERSION,
            expected_schema_version=JOURNAL_SCHEMA_VERSION,
        )
        journal.update_target_state(
            state,
            oid,
            canonical_path=target.canonical_path,
            state="physical_deleted",
            staging_path=str(staging),
            staged_dev=int(st.st_dev),
            staged_ino=int(st.st_ino),
        )
        journal.update_operation_status(state, oid, CleanupStatus.SUCCESS.value)
        loaded = journal.load_operation_typed(
            state,
            oid,
            expected_policy_version=CLEANUP_POLICY_VERSION,
            expected_schema_version=JOURNAL_SCHEMA_VERSION,
        )
        assert loaded.kind is journal.JournalLoadKind.TERMINAL
        assert journal.list_pending_staging(state) == []

    def test_corrupt_journal_payload(self, tmp_path):
        state = tmp_path / "state"
        ops = state / "cleanup" / "operations"
        ops.mkdir(parents=True)
        oid = "1_abcdefabcdef"
        (ops / f"{oid}.json").write_text("{not-json", encoding="utf-8")
        loaded = journal.load_operation_typed(
            state,
            oid,
            expected_policy_version=CLEANUP_POLICY_VERSION,
            expected_schema_version=JOURNAL_SCHEMA_VERSION,
        )
        assert loaded.kind is journal.JournalLoadKind.CORRUPT_OR_UNSAFE


class TestPathsOverlap:
    def test_overlap_relations(self, tmp_path):
        a = tmp_path / "a"
        b = a / "b"
        c = tmp_path / "c"
        a.mkdir()
        b.mkdir()
        c.mkdir()
        assert paths_overlap(a, b)
        assert paths_overlap(b, a)
        assert paths_overlap(a, a)
        assert not paths_overlap(a, c)
