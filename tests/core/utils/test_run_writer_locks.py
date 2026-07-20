"""Characterization tests for FileLock and RunWriterLock semantics."""

from __future__ import annotations

import multiprocessing
import threading
import time
from pathlib import Path


from transcriptx.core.utils.file_lock import FileLock, cleanup_stale_locks
from transcriptx.core.utils.run_writer_locks import (
    RunWriterLock,
    LockAcquisitionError,
    mutation_gate_lock_path,
    per_run_lock,
    run_lock_path_for_canonical_root,
    run_tree_mutation_gate,
    try_per_run_lock,
    try_run_tree_mutation_gate,
)


def _hold_lock(path_str: str, hold_seconds: float, result_queue) -> None:
    path = Path(path_str)
    lock = FileLock(path, timeout=5, blocking=True)
    ok = lock.acquire()
    result_queue.put(("acquired", ok))
    if ok:
        time.sleep(hold_seconds)
        lock.release()
        result_queue.put(("released", True))


class TestFileLockCharacterization:
    """Prove FileLock semantics needed by run-writer locks."""

    def test_cross_process_exclusion(self, tmp_path):
        target = tmp_path / "shared.txt"
        target.write_text("x", encoding="utf-8")
        ctx = multiprocessing.get_context("spawn")
        q = ctx.Queue()
        p = ctx.Process(target=_hold_lock, args=(str(target), 1.5, q))
        p.start()
        # Wait until child acquired
        assert q.get(timeout=5) == ("acquired", True)
        # Parent must not acquire non-blocking
        parent = FileLock(target, blocking=False)
        assert parent.acquire() is False
        p.join(timeout=5)
        assert p.exitcode == 0
        # After release, parent can acquire
        assert parent.acquire() is True
        parent.release()

    def test_cross_thread_exclusion(self, tmp_path):
        target = tmp_path / "thread.txt"
        target.write_text("x", encoding="utf-8")
        held = threading.Event()
        release = threading.Event()
        results: list[bool] = []

        def holder():
            with FileLock(target, timeout=5):
                held.set()
                release.wait(timeout=5)

        t = threading.Thread(target=holder)
        t.start()
        assert held.wait(timeout=5)
        other = FileLock(target, blocking=False)
        results.append(other.acquire())
        release.set()
        t.join(timeout=5)
        assert results == [False]

    def test_reentrant_same_thread(self, tmp_path):
        target = tmp_path / "re.txt"
        target.write_text("x", encoding="utf-8")
        with FileLock(target) as a:
            with FileLock(target) as b:
                assert a.acquired and b.acquired
            assert a.acquired
        assert not a.acquired

    def test_same_thread_acquire_is_reentrant(self, tmp_path):
        """Same-thread second FileLock succeeds via depth tracking (documented)."""
        target = tmp_path / "nb.txt"
        target.write_text("x", encoding="utf-8")
        with FileLock(target):
            other = FileLock(target, blocking=False)
            assert other.acquire() is True
            other.release()

    def test_non_blocking_acquire_cross_thread(self, tmp_path):
        target = tmp_path / "nb2.txt"
        target.write_text("x", encoding="utf-8")
        held = threading.Event()
        release = threading.Event()
        result: list[bool] = []

        def holder():
            with FileLock(target, timeout=5):
                held.set()
                release.wait(timeout=5)

        t = threading.Thread(target=holder)
        t.start()
        assert held.wait(timeout=5)
        other = FileLock(target, blocking=False)
        result.append(other.acquire())
        release.set()
        t.join(timeout=5)
        assert result == [False]

    def test_timeout_behaviour_cross_thread(self, tmp_path):
        target = tmp_path / "to.txt"
        target.write_text("x", encoding="utf-8")
        held = threading.Event()
        release = threading.Event()

        def holder():
            with FileLock(target, timeout=5):
                held.set()
                release.wait(timeout=5)

        t = threading.Thread(target=holder)
        t.start()
        assert held.wait(timeout=5)
        other = FileLock(target, timeout=0, blocking=True)
        start = time.time()
        assert other.acquire() is False
        assert time.time() - start < 2.0
        release.set()
        t.join(timeout=5)

    def test_exception_safe_release_via_context(self, tmp_path):
        target = tmp_path / "ex.txt"
        target.write_text("x", encoding="utf-8")
        try:
            with FileLock(target) as lock:
                assert lock.acquired
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        # Lock file should be gone / unlocked
        probe = FileLock(target, blocking=False)
        assert probe.acquire() is True
        probe.release()

    def test_stale_lock_file_cleanup(self, tmp_path):
        lock_file = tmp_path / "doc.txt.lock"
        lock_file.write_text("stale", encoding="utf-8")
        import os

        old = time.time() - 10_000
        os.utime(lock_file, (old, old))
        cleanup_stale_locks(lock_file, max_age_seconds=3600)
        assert not lock_file.exists()
        # Held flock is not broken by stale-file helper alone; after cleanup,
        # a new lock can be acquired.
        target = tmp_path / "doc.txt"
        target.write_text("x", encoding="utf-8")
        with FileLock(target):
            assert True


class TestRunWriterLock:
    def test_lock_path_outside_run_tree(self, tmp_path):
        state = tmp_path / "state"
        run = tmp_path / "outputs" / "slug" / "run1"
        path = run_lock_path_for_canonical_root(run, state_dir=state)
        assert path.is_relative_to(state)
        assert "run_locks" in path.parts
        assert not path.is_relative_to(tmp_path / "outputs")

    def test_mutation_gate_path(self, tmp_path):
        p = mutation_gate_lock_path(tmp_path / "state")
        assert p.name == "run_tree_mutation.lock"

    def test_try_acquire_and_exclusion_cross_thread(self, tmp_path):
        state = tmp_path / "state"
        run = tmp_path / "out" / "s" / "r"
        held = threading.Event()
        release = threading.Event()
        probe: list[object] = []

        def holder():
            with per_run_lock(run, state_dir=state):
                held.set()
                release.wait(timeout=5)

        t = threading.Thread(target=holder)
        t.start()
        assert held.wait(timeout=5)
        probe.append(try_per_run_lock(run, state_dir=state))
        release.set()
        t.join(timeout=5)
        assert probe == [None]
        got = try_per_run_lock(run, state_dir=state)
        assert got is not None
        got.release()

    def test_mutation_gate_try_cross_thread(self, tmp_path):
        state = tmp_path / "state"
        held = threading.Event()
        release = threading.Event()
        probe: list[object] = []

        def holder():
            with run_tree_mutation_gate(state_dir=state):
                held.set()
                release.wait(timeout=5)

        t = threading.Thread(target=holder)
        t.start()
        assert held.wait(timeout=5)
        probe.append(try_run_tree_mutation_gate(state_dir=state))
        release.set()
        t.join(timeout=5)
        assert probe == [None]
        lock = try_run_tree_mutation_gate(state_dir=state)
        assert lock is not None
        lock.release()

    def test_blocking_raises_cross_thread(self, tmp_path):
        state = tmp_path / "state"
        run = tmp_path / "out" / "s" / "r"
        path = run_lock_path_for_canonical_root(run, state_dir=state)
        path.parent.mkdir(parents=True, exist_ok=True)
        held = threading.Event()
        release = threading.Event()
        err: list[BaseException] = []

        def holder():
            lock = RunWriterLock(path, blocking=True)
            lock.acquire()
            held.set()
            release.wait(timeout=5)
            lock.release()

        def waiter():
            try:
                with RunWriterLock(path, timeout=0.2, blocking=True):
                    pass
            except BaseException as e:
                err.append(e)

        t = threading.Thread(target=holder)
        t.start()
        assert held.wait(timeout=5)
        w = threading.Thread(target=waiter)
        w.start()
        w.join(timeout=5)
        release.set()
        t.join(timeout=5)
        assert len(err) == 1
        assert isinstance(err[0], LockAcquisitionError)


class TestBoundRunWriterLease:
    def test_worker_thread_write_uses_bound_lease(self, tmp_path, monkeypatch):
        """Orchestrator holds lock on main; timeout worker must not re-acquire."""
        import concurrent.futures
        import contextvars

        from transcriptx.core.output.output_service import OutputService
        from transcriptx.core.utils.run_writer_locks import (
            bind_run_writer_lease,
            per_run_lock,
        )

        # Keep writes under tmp_path (avoid redirect into real OUTPUTS_DIR).
        monkeypatch.setenv("TRANSCRIPTX_OUTPUT_DIR", str(tmp_path / "outputs"))
        monkeypatch.setenv("TRANSCRIPTX_DATA_DIR", str(tmp_path / "data"))

        run = tmp_path / "outputs" / "slug" / "run1"
        run.mkdir(parents=True)
        (run / ".transcriptx").mkdir()
        (tmp_path / "data" / "state" / "run_locks").mkdir(parents=True)

        written: list[str] = []

        def worker() -> None:
            svc = OutputService(
                transcript_path=str(tmp_path / "t.json"),
                module_name="tics",
                output_dir=str(run),
            )
            written.append(
                svc.save_data({"ok": True}, "tics_summary", format_type="json")
            )

        with per_run_lock(run, state_dir=tmp_path / "data" / "state") as lock:
            with bind_run_writer_lease(lock.lease()):
                ctx = contextvars.copy_context()
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    ex.submit(ctx.run, worker).result(timeout=5)

        assert written and Path(written[0]).exists()
