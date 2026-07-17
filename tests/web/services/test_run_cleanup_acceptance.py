"""Acceptance and race tests for bulk run cleanup (release-blocking)."""

from __future__ import annotations

import hashlib
import os
import threading
from pathlib import Path

import pytest

from transcriptx.core.utils.run_writer_locks import (
    per_run_lock,
    run_tree_mutation_gate,
    try_run_tree_mutation_gate,
)
from transcriptx.web.services.run_cleanup import (
    CONFIRM_DELETE_ALL,
    CONFIRM_DELETE_OLD,
    CleanupAuthorization,
    CleanupMode,
    CleanupStatus,
    RunCleanupService,
    STAGING_DIR_NAME,
    TargetStatus,
)
from transcriptx.web.services.run_cleanup import journal as cleanup_journal
from transcriptx.web.services.run_cleanup.physical_delete import (
    PhysicalDeleteUnsafeError,
    safe_rmtree,
)
from transcriptx.web.services.run_cleanup.session_clear import (
    clear_session_selections_for_removed_runs,
)


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
    # Protected trees under data
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


def _checksum_tree(root: Path) -> str:
    h = hashlib.sha256()
    if not root.exists():
        return h.hexdigest()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            p = Path(dirpath) / name
            rel = p.relative_to(root).as_posix()
            h.update(rel.encode())
            try:
                h.update(p.read_bytes())
            except OSError:
                h.update(b"?")
    return h.hexdigest()


class TestCleanupHappyPath:
    def test_delete_all_and_checksum_gate(self, tmp_path):
        svc = _svc(tmp_path)
        out = svc.outputs_dir
        data = svc.data_dir
        # Protected content
        (data / "transcripts" / "t.json").write_text('{"ok":1}', encoding="utf-8")
        (data / "corrections" / "c.json").write_text("{}", encoding="utf-8")
        (data / "groups" / "g.group.json").write_text("{}", encoding="utf-8")
        index = out / ".transcriptx_index.json"
        index.write_text('{"slugs":{}}', encoding="utf-8")
        before = {
            "transcripts": _checksum_tree(data / "transcripts"),
            "corrections": _checksum_tree(data / "corrections"),
            "groups": _checksum_tree(data / "groups"),
            "index": index.read_text(encoding="utf-8"),
        }
        _mk_run(out, "slug_a", "20200101_000000_00000001")
        _mk_run(out, "slug_a", "20200101_000000_00000002")
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")
        assert preview.run_count == 2
        assert preview.can_execute
        result = svc.execute_cleanup(
            handle, _auth(CleanupMode.DELETE_ALL, preview.plan_id), "s1"
        )
        assert result.status is CleanupStatus.SUCCESS
        assert result.visible_removed_count == 2
        assert result.physically_deleted_count == 2
        assert not (out / "slug_a" / "20200101_000000_00000001").exists()
        assert not (out / "slug_a" / "20200101_000000_00000002").exists()
        assert before["transcripts"] == _checksum_tree(data / "transcripts")
        assert before["corrections"] == _checksum_tree(data / "corrections")
        assert before["groups"] == _checksum_tree(data / "groups")
        assert before["index"] == index.read_text(encoding="utf-8")

    def test_delete_old_keeps_newest(self, tmp_path):
        svc = _svc(tmp_path)
        out = svc.outputs_dir
        older = _mk_run(out, "slug_b", "20200101_000000_00000001", "old")
        newer = _mk_run(out, "slug_b", "20200101_000000_00000002", "new")
        # Ensure newer mtime
        os.utime(older, (1_000_000, 1_000_000))
        os.utime(newer, (2_000_000, 2_000_000))
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_OLD, "s1")
        assert preview.run_count == 1
        assert len(preview.retained) == 1
        assert preview.retained[0]["run_id"] == "20200101_000000_00000002"
        result = svc.execute_cleanup(
            handle, _auth(CleanupMode.DELETE_OLD, preview.plan_id), "s1"
        )
        assert result.status is CleanupStatus.SUCCESS
        assert not older.exists()
        assert newer.exists()

    def test_auth_rejects_trimmed_phrase(self, tmp_path):
        svc = _svc(tmp_path)
        _mk_run(svc.outputs_dir, "slug_c", "20200101_000000_00000001")
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")
        bad = CleanupAuthorization(
            acknowledged=True,
            phrase=" DELETE ALL",
            mode=CleanupMode.DELETE_ALL,
            plan_id=preview.plan_id,
        )
        result = svc.execute_cleanup(handle, bad, "s1")
        assert result.status is CleanupStatus.BLOCKED
        assert (svc.outputs_dir / "slug_c" / "20200101_000000_00000001").exists()


class TestCleanupRaces:
    def test_mutation_gate_blocks_create_during_cleanup(self, tmp_path):
        svc = _svc(tmp_path)
        _mk_run(svc.outputs_dir, "slug_d", "20200101_000000_00000001")
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")
        blocked: list[bool] = []
        release_cleanup = threading.Event()
        in_cleanup = threading.Event()

        def run_cleanup():
            # Hold gate manually then execute path that also needs gate —
            # simulate long cleanup by holding gate while create tries.
            with run_tree_mutation_gate(state_dir=svc.state_dir):
                in_cleanup.set()
                release_cleanup.wait(timeout=5)
            # After release, execute for real
            svc.execute_cleanup(
                handle, _auth(CleanupMode.DELETE_ALL, preview.plan_id), "s1"
            )

        def try_create():
            assert in_cleanup.wait(timeout=5)
            gate = try_run_tree_mutation_gate(state_dir=svc.state_dir)
            blocked.append(gate is None)
            release_cleanup.set()

        t1 = threading.Thread(target=run_cleanup)
        t2 = threading.Thread(target=try_create)
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)
        assert blocked == [True]

    def test_fingerprint_detects_descendant_change(self, tmp_path):
        svc = _svc(tmp_path)
        run = _mk_run(svc.outputs_dir, "slug_e", "20200101_000000_00000001", "v1")
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")
        # Change descendant without touching run-root mtime
        root_mtime = run.stat().st_mtime
        (run / "artifact.txt").write_text("v2-changed", encoding="utf-8")
        os.utime(run, (root_mtime, root_mtime))
        result = svc.execute_cleanup(
            handle, _auth(CleanupMode.DELETE_ALL, preview.plan_id), "s1"
        )
        assert result.status is CleanupStatus.STALE_PLAN
        assert run.exists()

    def test_delete_old_subject_skip_when_retained_locked(self, tmp_path):
        svc = _svc(tmp_path)
        out = svc.outputs_dir
        older = _mk_run(out, "slug_f", "20200101_000000_00000001")
        newer = _mk_run(out, "slug_f", "20200101_000000_00000002")
        os.utime(older, (1_000_000, 1_000_000))
        os.utime(newer, (2_000_000, 2_000_000))
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_OLD, "s1")
        held = threading.Event()
        release = threading.Event()
        result_box: list = []

        def holder():
            with per_run_lock(newer, state_dir=svc.state_dir):
                held.set()
                release.wait(timeout=10)

        def executor():
            assert held.wait(timeout=5)
            result_box.append(
                svc.execute_cleanup(
                    handle, _auth(CleanupMode.DELETE_OLD, preview.plan_id), "s1"
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
        assert any(t.status is TargetStatus.SUBJECT_LOCKED_SKIP for t in result.targets)
        assert older.exists() and newer.exists()
        # Subject must not partially delete older while retained locked
        assert older.exists()

    def test_concurrent_handle_claim(self, tmp_path):
        svc = _svc(tmp_path)
        _mk_run(svc.outputs_dir, "slug_g", "20200101_000000_00000001")
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")
        results: list = []
        barrier = threading.Barrier(2)

        def worker():
            barrier.wait(timeout=5)
            results.append(
                svc.execute_cleanup(
                    handle, _auth(CleanupMode.DELETE_ALL, preview.plan_id), "s1"
                )
            )

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)
        statuses = {r.status for r in results}
        mutating = [
            r
            for r in results
            if r.status
            in {CleanupStatus.SUCCESS, CleanupStatus.PARTIAL, CleanupStatus.NOOP}
        ]
        already = [r for r in results if r.status is CleanupStatus.ALREADY_EXECUTED]
        assert len(mutating) == 1
        assert len(already) == 1
        assert CleanupStatus.ALREADY_EXECUTED in statuses

    def test_fake_staging_without_journal_never_removed(self, tmp_path):
        svc = _svc(tmp_path)
        fake = svc.outputs_dir / STAGING_DIR_NAME / "bogus" / "run"
        fake.mkdir(parents=True, exist_ok=True)
        (fake / "x.txt").write_text("keep", encoding="utf-8")
        # retry path should not delete without journal
        pending = cleanup_journal.list_pending_staging(svc.state_dir)
        assert all(
            Path(p.get("staging_path", "")).resolve() != fake.resolve()
            for p in pending
            if p.get("staging_path")
        )
        assert fake.exists()
        assert not cleanup_journal.is_journal_recognised_staging_path(
            svc.state_dir,
            fake,
            operation_id="1_abcdefabcdef",
            subject_type="transcript",
            subject_id="x",
            run_id="y",
            canonical_path="/nope",
            outputs_dir=svc.outputs_dir,
            group_outputs_dir=svc.group_outputs_dir,
        )
        # Direct safe_rmtree is refused unconditionally; journal
        # retry must never select this path. Keep fake intact.
        assert fake.exists()
        assert (fake / "x.txt").read_text(encoding="utf-8") == "keep"
        # Bare-path delete API is refused
        with pytest.raises(PhysicalDeleteUnsafeError):
            safe_rmtree(fake)
        assert fake.exists()

    def test_stale_plan_never_renames(self, tmp_path):
        svc = _svc(tmp_path)
        run = _mk_run(svc.outputs_dir, "slug_stale", "20200101_000000_00000001", "v1")
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")
        (run / "artifact.txt").write_text("changed", encoding="utf-8")
        rename_count = {"n": 0}
        real_rename = os.rename

        def counting_rename(src, dst, *args, **kwargs):
            rename_count["n"] += 1
            return real_rename(src, dst, *args, **kwargs)

        monkey = pytest.MonkeyPatch()
        monkey.setattr(os, "rename", counting_rename)
        try:
            result = svc.execute_cleanup(
                handle, _auth(CleanupMode.DELETE_ALL, preview.plan_id), "s1"
            )
        finally:
            monkey.undo()
        assert result.status is CleanupStatus.STALE_PLAN
        assert rename_count["n"] == 0
        assert run.exists()

    def test_fault_before_rename_leaves_source(self, tmp_path):
        from transcriptx.web.services.run_cleanup import faults

        svc = _svc(tmp_path)
        run = _mk_run(svc.outputs_dir, "slug_fault", "20200101_000000_00000001")
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")

        def boom():
            raise RuntimeError("injected before rename")

        faults.set_fault_hook("before_first_rename", boom)
        try:
            result = svc.execute_cleanup(
                handle, _auth(CleanupMode.DELETE_ALL, preview.plan_id), "s1"
            )
            # Fault may be converted to FAILED_BEFORE_MUTATION by finalisation
            assert result.status is CleanupStatus.FAILED_BEFORE_MUTATION
            assert any("injected before rename" in e for e in result.errors)
        finally:
            faults.clear_fault_hooks()
        assert run.exists()

    def test_shared_builder_signature_stable(self, tmp_path):
        from transcriptx.web.services.run_cleanup.plan_builder import (
            build_execution_set,
            execution_set_signature,
        )

        from transcriptx.web.services.run_cleanup.path_helpers import validate_roots

        svc = _svc(tmp_path)
        _mk_run(svc.outputs_dir, "slug_sig", "20200101_000000_00000001")
        roots, blocking = validate_roots(svc)
        a = build_execution_set(
            CleanupMode.DELETE_ALL,
            roots,
            blocking,
            svc.outputs_dir,
            svc.group_outputs_dir,
        )
        b = build_execution_set(
            CleanupMode.DELETE_ALL,
            roots,
            blocking,
            svc.outputs_dir,
            svc.group_outputs_dir,
        )
        assert execution_set_signature(a) == execution_set_signature(b)
        assert a.candidates == b.candidates

    def test_idempotent_second_execute(self, tmp_path):
        svc = _svc(tmp_path)
        _mk_run(svc.outputs_dir, "slug_h", "20200101_000000_00000001")
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")
        auth = _auth(CleanupMode.DELETE_ALL, preview.plan_id)
        r1 = svc.execute_cleanup(handle, auth, "s1")
        r2 = svc.execute_cleanup(handle, auth, "s1")
        assert r1.status is CleanupStatus.SUCCESS
        assert r2.status is CleanupStatus.ALREADY_EXECUTED
        assert r1.visible_removed_count == 1
        assert r1.physically_deleted_count == 1

    def test_session_clear_matches_full_identity(self, tmp_path):
        from transcriptx.web.services.run_cleanup.models import (
            CleanupTargetResult,
            SubjectType,
        )

        session = {
            "subject_type": "transcript",
            "subject_id": "slug_i",
            "run_id": "20200101_000000_00000001",
            "selected_run_dir": None,
        }
        # Same run_id different subject must not clear
        other = CleanupTargetResult(
            subject_type=SubjectType.transcript,
            subject_id="other_slug",
            run_id="20200101_000000_00000001",
            root_relative_path="other_slug/20200101_000000_00000001",
            canonical_path="/tmp/x",
            status=TargetStatus.PHYSICAL_DELETED,
        )
        assert clear_session_selections_for_removed_runs(session, [other]) is False
        assert session["run_id"] == "20200101_000000_00000001"
        match = CleanupTargetResult(
            subject_type=SubjectType.transcript,
            subject_id="slug_i",
            run_id="20200101_000000_00000001",
            root_relative_path="slug_i/20200101_000000_00000001",
            canonical_path="/tmp/y",
            status=TargetStatus.PHYSICAL_DELETED,
        )
        assert clear_session_selections_for_removed_runs(session, [match]) is True
        assert session.get("run_id") is None

    def test_legacy_noncanonical_excluded(self, tmp_path):
        svc = _svc(tmp_path)
        # Legacy: files directly under slug without run_id shape as only child dir
        legacy = svc.outputs_dir / "slug_legacy"
        legacy.mkdir(parents=True)
        (legacy / "report.json").write_text("{}", encoding="utf-8")
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")
        assert preview.run_count == 0
        # May have exclusions for unknown layout
        assert (legacy / "report.json").exists()

    def test_cache_invalidation_failure_still_reports_removal(self, tmp_path):
        def boom():
            raise RuntimeError("cache boom")

        svc = _svc(tmp_path, cache_invalidator=boom)
        run = _mk_run(svc.outputs_dir, "slug_j", "20200101_000000_00000001")
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "s1")
        result = svc.execute_cleanup(
            handle, _auth(CleanupMode.DELETE_ALL, preview.plan_id), "s1"
        )
        assert result.status is CleanupStatus.SUCCESS
        assert result.visible_removed_count == 1
        assert result.physically_deleted_count == 1
        assert not run.exists()
        assert any(
            "cache" in w.lower() or "invalidat" in w.lower() for w in result.warnings
        )

    def test_delete_old_subject_skip_when_older_locked(self, tmp_path):
        svc = _svc(tmp_path)
        out = svc.outputs_dir
        older = _mk_run(out, "slug_old_lock", "20200101_000000_00000001")
        newer = _mk_run(out, "slug_old_lock", "20200101_000000_00000002")
        os.utime(older, (1_000_000, 1_000_000))
        os.utime(newer, (2_000_000, 2_000_000))
        handle, preview = svc.preview_cleanup(CleanupMode.DELETE_OLD, "s1")
        held = threading.Event()
        release = threading.Event()
        result_box: list = []

        def holder():
            with per_run_lock(older, state_dir=svc.state_dir):
                held.set()
                release.wait(timeout=10)

        def executor():
            assert held.wait(timeout=5)
            result_box.append(
                svc.execute_cleanup(
                    handle, _auth(CleanupMode.DELETE_OLD, preview.plan_id), "s1"
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
        assert any(t.status is TargetStatus.SUBJECT_LOCKED_SKIP for t in result.targets)
        assert older.exists() and newer.exists()
        assert result.visible_removed_count == 0


class TestPhysicalDelete:
    def test_refuses_non_staging_path(self, tmp_path):
        p = tmp_path / "not_staging"
        p.mkdir()
        with pytest.raises(PhysicalDeleteUnsafeError):
            safe_rmtree(p)
