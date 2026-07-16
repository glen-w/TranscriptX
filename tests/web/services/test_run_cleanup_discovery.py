"""Classifier, fingerprint, and plan-builder discovery contracts."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

from transcriptx.web.services.run_cleanup.classifier import RunRootClassifier
from transcriptx.web.services.run_cleanup.fingerprint import (
    TreeFingerprintError,
    compute_tree_fingerprint,
)
from transcriptx.web.services.run_cleanup.models import (
    CleanupMode,
    CleanupTarget,
    EntryClassification,
    RootIdentity,
    STAGING_DIR_NAME,
    SubjectType,
)
from transcriptx.web.services.run_cleanup.plan_builder import (
    build_execution_set,
    execution_set_signature,
    execution_set_to_plan,
    partition_for_mode,
)


def _root_identity(kind: SubjectType, path: Path) -> RootIdentity:
    st = path.stat()
    return RootIdentity(
        kind=kind,
        configured_path=str(path),
        canonical_path=str(path.resolve()),
        dev=int(st.st_dev),
        ino=int(st.st_ino),
        is_symlink=False,
        exists=True,
    )


def _mk_run(root: Path, subject: str, run_id: str, content: str = "x") -> Path:
    run = root / subject / run_id
    run.mkdir(parents=True, exist_ok=True)
    (run / "artifact.txt").write_text(content, encoding="utf-8")
    return run


class TestRunRootClassifier:
    def test_discovers_transcript_and_group_runs(self, tmp_path):
        outputs = tmp_path / "outputs"
        groups = outputs / "groups"
        outputs.mkdir()
        groups.mkdir()
        gid = str(uuid.UUID("aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"))
        _mk_run(outputs, "slug_ok", "20200101_000000_00000001")
        _mk_run(groups, gid, "20200101_000000_00000002")
        roots = [
            _root_identity(SubjectType.transcript, outputs),
            _root_identity(SubjectType.group, groups),
        ]
        targets, exclusions = RunRootClassifier.discover(outputs, groups, roots)
        assert len(targets) == 2
        kinds = {(t.subject_type, t.subject_id, t.run_id) for t in targets}
        assert (SubjectType.transcript, "slug_ok", "20200101_000000_00000001") in kinds
        assert (SubjectType.group, gid, "20200101_000000_00000002") in kinds
        # Nested groups dir under outputs is skipped, not double-counted
        assert not any(e.path_relative == "groups" for e in exclusions)

    def test_excludes_invalid_slug_symlink_staging_and_file(self, tmp_path):
        outputs = tmp_path / "outputs"
        groups = tmp_path / "groups"
        outputs.mkdir()
        groups.mkdir()
        _mk_run(outputs, "valid_slug", "20200101_000000_00000001")
        bad_slug = outputs / "Bad Slug!"
        bad_slug.mkdir()
        (bad_slug / "20200101_000000_00000001").mkdir()
        link = outputs / "linked_slug"
        link.symlink_to(outputs / "valid_slug")
        staging = outputs / STAGING_DIR_NAME
        staging.mkdir()
        (outputs / "orphan.txt").write_text("nope", encoding="utf-8")
        # Invalid run_id under valid slug
        (outputs / "valid_slug" / "not a run").mkdir()
        roots = [
            _root_identity(SubjectType.transcript, outputs),
            _root_identity(SubjectType.group, groups),
        ]
        targets, exclusions = RunRootClassifier.discover(outputs, groups, roots)
        assert len(targets) == 1
        by_class = {e.classification for e in exclusions}
        assert EntryClassification.invalid in by_class
        assert EntryClassification.symlink in by_class
        assert EntryClassification.staging in by_class
        assert EntryClassification.unknown in by_class
        assert any("invalid transcript slug" in e.reason for e in exclusions)
        assert any("invalid run_id" in e.reason for e in exclusions)

    def test_excludes_invalid_group_uuid(self, tmp_path):
        outputs = tmp_path / "outputs"
        groups = tmp_path / "groups"
        outputs.mkdir()
        groups.mkdir()
        _mk_run(groups, "not-a-uuid", "20200101_000000_00000001")
        roots = [
            _root_identity(SubjectType.transcript, outputs),
            _root_identity(SubjectType.group, groups),
        ]
        targets, exclusions = RunRootClassifier.discover(outputs, groups, roots)
        assert targets == []
        assert any(
            e.classification is EntryClassification.invalid
            and "invalid group uuid" in e.reason
            for e in exclusions
        )

    def test_symlink_under_run_tree_excludes_entire_run(self, tmp_path):
        outputs = tmp_path / "outputs"
        groups = tmp_path / "groups"
        outputs.mkdir()
        groups.mkdir()
        run = _mk_run(outputs, "slug_sym", "20200101_000000_00000001")
        (run / "link.txt").symlink_to(run / "artifact.txt")
        roots = [
            _root_identity(SubjectType.transcript, outputs),
            _root_identity(SubjectType.group, groups),
        ]
        targets, exclusions = RunRootClassifier.discover(outputs, groups, roots)
        assert targets == []
        assert any(e.classification is EntryClassification.symlink for e in exclusions)


class TestTreeFingerprint:
    def test_stable_across_same_content_and_changes_on_edit(self, tmp_path):
        run = tmp_path / "run"
        run.mkdir()
        (run / "a.txt").write_text("one", encoding="utf-8")
        (run / "sub").mkdir()
        (run / "sub" / "b.txt").write_text("two", encoding="utf-8")
        dev = int(run.stat().st_dev)
        fp1, size1, count1 = compute_tree_fingerprint(run, dev)
        fp2, size2, count2 = compute_tree_fingerprint(run, dev)
        assert fp1 == fp2
        assert size1 == size2 == 6
        assert count1 == count2 == 2
        (run / "a.txt").write_text("changed", encoding="utf-8")
        fp3, _, _ = compute_tree_fingerprint(run, dev)
        assert fp3 != fp1

    def test_rejects_symlink_and_wrong_device(self, tmp_path):
        run = tmp_path / "run"
        run.mkdir()
        (run / "a.txt").write_text("x", encoding="utf-8")
        (run / "l").symlink_to(run / "a.txt")
        dev = int(run.stat().st_dev)
        with pytest.raises(TreeFingerprintError) as exc:
            compute_tree_fingerprint(run, dev)
        assert exc.value.classification == "symlink"
        with pytest.raises(TreeFingerprintError) as exc2:
            compute_tree_fingerprint(run, root_dev=dev + 999_999)
        assert exc2.value.classification == "cross_device"

    def test_fingerprint_ignores_run_root_rename(self, tmp_path):
        """Descendant fingerprint must stay stable across same-FS rename of root."""
        src = tmp_path / "src_run"
        src.mkdir()
        (src / "artifact.txt").write_text("payload", encoding="utf-8")
        dev = int(src.stat().st_dev)
        before, size, count = compute_tree_fingerprint(src, dev)
        dst = tmp_path / "dst_run"
        os.rename(src, dst)
        after, size2, count2 = compute_tree_fingerprint(dst, dev)
        assert before == after
        assert size == size2
        assert count == count2 == 1


class TestPlanBuilder:
    def _target(
        self,
        subject_id: str,
        run_id: str,
        *,
        mtime_ns: int,
        subject_type: SubjectType = SubjectType.transcript,
        fingerprint: str = "a" * 64,
        ino: int = 1,
    ) -> CleanupTarget:
        return CleanupTarget(
            subject_type=subject_type,
            subject_id=subject_id,
            run_id=run_id,
            root_relative_path=f"{subject_id}/{run_id}",
            canonical_path=f"/o/{subject_id}/{run_id}",
            mtime_ns=mtime_ns,
            filesystem_dev=1,
            filesystem_ino=ino,
            size_estimate_bytes=1,
            file_count=1,
            tree_fingerprint=fingerprint,
            safety_status=EntryClassification.eligible,
        )

    def test_partition_delete_all_retains_nothing(self):
        eligible = [
            self._target("a", "20200101_000000_00000001", mtime_ns=1, ino=1),
            self._target("a", "20200101_000000_00000002", mtime_ns=2, ino=2),
        ]
        candidates, retained = partition_for_mode(CleanupMode.DELETE_ALL, eligible)
        assert len(candidates) == 2
        assert retained == []

    def test_partition_delete_old_keeps_newest_per_subject(self):
        eligible = [
            self._target("alpha", "20200101_000000_00000001", mtime_ns=1_000, ino=1),
            self._target("alpha", "20200101_000000_00000002", mtime_ns=2_000, ino=2),
            self._target("beta", "20200101_000000_00000003", mtime_ns=5_000, ino=3),
            self._target(
                "beta",
                "20200101_000000_00000004",
                mtime_ns=4_000,
                ino=4,
                subject_type=SubjectType.group,
            ),
        ]
        # Same subject_id different types are independent subjects
        candidates, retained = partition_for_mode(CleanupMode.DELETE_OLD, eligible)
        retained_keys = {(t.subject_type, t.subject_id, t.run_id) for t in retained}
        candidate_keys = {(t.subject_type, t.subject_id, t.run_id) for t in candidates}
        assert retained_keys == {
            (SubjectType.transcript, "alpha", "20200101_000000_00000002"),
            (SubjectType.transcript, "beta", "20200101_000000_00000003"),
            (SubjectType.group, "beta", "20200101_000000_00000004"),
        }
        assert candidate_keys == {
            (SubjectType.transcript, "alpha", "20200101_000000_00000001"),
        }

    def test_partition_mtime_tie_breaks_on_run_id(self):
        eligible = [
            self._target("s", "20200101_000000_00000001", mtime_ns=100, ino=1),
            self._target("s", "20200101_000000_00000002", mtime_ns=100, ino=2),
        ]
        candidates, retained = partition_for_mode(CleanupMode.DELETE_OLD, eligible)
        assert len(retained) == 1
        assert retained[0].run_id == "20200101_000000_00000002"
        assert candidates[0].run_id == "20200101_000000_00000001"

    def test_blocking_skips_discovery(self, tmp_path):
        outputs = tmp_path / "outputs"
        groups = tmp_path / "groups"
        outputs.mkdir()
        groups.mkdir()
        _mk_run(outputs, "slug_x", "20200101_000000_00000001")
        roots = [
            _root_identity(SubjectType.transcript, outputs),
            _root_identity(SubjectType.group, groups),
        ]
        es = build_execution_set(
            CleanupMode.DELETE_ALL,
            roots,
            ["roots unsafe"],
            outputs,
            groups,
        )
        assert es.can_execute is False
        assert es.candidates == ()
        assert es.eligible == ()
        assert "discovery skipped" in es.warnings[0].lower()
        plan = execution_set_to_plan(es)
        assert plan.can_execute is False
        assert plan.blocking_errors == ("roots unsafe",)

    def test_empty_delete_old_still_executable(self, tmp_path):
        outputs = tmp_path / "outputs"
        groups = tmp_path / "groups"
        outputs.mkdir()
        groups.mkdir()
        roots = [
            _root_identity(SubjectType.transcript, outputs),
            _root_identity(SubjectType.group, groups),
        ]
        es = build_execution_set(CleanupMode.DELETE_OLD, roots, [], outputs, groups)
        assert es.can_execute is True
        assert es.candidates == ()

    def test_signature_changes_when_fingerprint_changes(self, tmp_path):
        outputs = tmp_path / "outputs"
        groups = tmp_path / "groups"
        outputs.mkdir()
        groups.mkdir()
        run = _mk_run(outputs, "slug_sig", "20200101_000000_00000001", "v1")
        roots = [
            _root_identity(SubjectType.transcript, outputs),
            _root_identity(SubjectType.group, groups),
        ]
        a = build_execution_set(CleanupMode.DELETE_ALL, roots, [], outputs, groups)
        (run / "artifact.txt").write_text("v2", encoding="utf-8")
        b = build_execution_set(CleanupMode.DELETE_ALL, roots, [], outputs, groups)
        assert execution_set_signature(a) != execution_set_signature(b)
