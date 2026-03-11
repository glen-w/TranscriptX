"""
Unit tests for app.progress:
  - make_initial_snapshot
  - update_snapshot_from_event (all event types)
  - _refresh_pct
  - SnapshotLogHandler.emit
"""

from __future__ import annotations

import logging

import pytest

from transcriptx.app.progress import (
    NullProgress,
    ProgressCallback,
    ProgressSnapshot,
    SnapshotLogHandler,
    _refresh_pct,
    make_initial_snapshot,
    update_snapshot_from_event,
)


@pytest.mark.unit
class TestMakeInitialSnapshot:
    def test_returns_running_status(self):
        snap = make_initial_snapshot(total=3)
        assert snap["status"] == "running"

    def test_phase_is_validating(self):
        snap = make_initial_snapshot(total=3)
        assert snap["phase"] == "validating"

    def test_total_is_set(self):
        snap = make_initial_snapshot(total=5)
        assert snap["total"] == 5

    def test_counts_are_zero(self):
        snap = make_initial_snapshot(total=3)
        assert snap["completed"] == 0
        assert snap["skipped"] == 0
        assert snap["failed"] == 0
        assert snap["pct"] == 0.0

    def test_recent_logs_is_empty_list(self):
        snap = make_initial_snapshot(total=3)
        assert snap["recent_logs"] == []

    def test_error_is_none(self):
        snap = make_initial_snapshot(total=3)
        assert snap["error"] is None

    def test_current_module_is_empty(self):
        snap = make_initial_snapshot(total=3)
        assert snap["current_module"] == ""


@pytest.mark.unit
class TestRefreshPct:
    def test_no_total_does_not_raise(self):
        snap: ProgressSnapshot = ProgressSnapshot(total=0, completed=0, skipped=0, failed=0)
        _refresh_pct(snap)  # should not raise

    def test_pct_computed_correctly(self):
        snap: ProgressSnapshot = ProgressSnapshot(total=4, completed=2, skipped=1, failed=0)
        _refresh_pct(snap)
        assert snap["pct"] == pytest.approx(75.0)

    def test_pct_capped_at_100(self):
        snap: ProgressSnapshot = ProgressSnapshot(total=2, completed=2, skipped=2, failed=2)
        _refresh_pct(snap)
        assert snap["pct"] <= 100.0


@pytest.mark.unit
class TestUpdateSnapshotFromEvent:
    def _snap(self, total: int = 3) -> ProgressSnapshot:
        return make_initial_snapshot(total=total)

    # --- run_started ---

    def test_run_started_sets_running(self):
        snap = self._snap()
        update_snapshot_from_event(snap, {"event": "run_started", "message": "Go"})
        assert snap["status"] == "running"
        assert snap["phase"] == "running_pipeline"
        assert snap["latest_event"] == "Go"

    def test_run_started_default_message(self):
        snap = self._snap()
        update_snapshot_from_event(snap, {"event": "run_started"})
        assert "started" in snap["latest_event"].lower()

    # --- module_started ---

    def test_module_started_sets_current_module(self):
        snap = self._snap()
        update_snapshot_from_event(
            snap,
            {"event": "module_started", "module_name": "stats", "index": 1, "total": 3},
        )
        assert snap["current_module"] == "stats"
        assert snap["phase"] == "running_pipeline"
        assert "stats" in snap["latest_event"]

    def test_module_started_no_index(self):
        snap = self._snap()
        update_snapshot_from_event(
            snap, {"event": "module_started", "module_name": "ner"}
        )
        assert "ner" in snap["latest_event"]

    # --- module_completed ---

    def test_module_completed_increments_count(self):
        snap = self._snap(total=3)
        update_snapshot_from_event(
            snap,
            {
                "event": "module_completed",
                "module_name": "stats",
                "completed": 1,
                "skipped": 0,
                "failed": 0,
                "index": 1,
                "total": 3,
            },
        )
        assert snap["completed"] == 1
        assert snap["pct"] == pytest.approx(100 / 3, rel=1e-3)

    def test_module_completed_includes_duration(self):
        snap = self._snap()
        update_snapshot_from_event(
            snap,
            {
                "event": "module_completed",
                "module_name": "stats",
                "completed": 1,
                "skipped": 0,
                "failed": 0,
                "duration_ms": 2500,
            },
        )
        assert "2.5s" in snap["latest_event"]

    # --- module_skipped ---

    def test_module_skipped_increments_skipped(self):
        snap = self._snap(total=2)
        update_snapshot_from_event(
            snap,
            {
                "event": "module_skipped",
                "module_name": "emotion",
                "skipped": 1,
                "completed": 0,
                "failed": 0,
                "message": "no data",
                "index": 1,
                "total": 2,
            },
        )
        assert snap["skipped"] == 1
        assert "emotion" in snap["latest_event"]
        assert "no data" in snap["latest_event"]

    # --- module_failed ---

    def test_module_failed_increments_failed(self):
        snap = self._snap(total=2)
        update_snapshot_from_event(
            snap,
            {
                "event": "module_failed",
                "module_name": "ner",
                "failed": 1,
                "completed": 0,
                "skipped": 0,
                "error": "timeout",
            },
        )
        assert snap["failed"] == 1
        assert snap["current_module"] == "ner"
        assert snap["error"] == "timeout"
        assert "timeout" in snap["latest_event"]

    def test_module_failed_no_error_does_not_set_error_key(self):
        snap = self._snap()
        update_snapshot_from_event(
            snap,
            {
                "event": "module_failed",
                "module_name": "ner",
                "failed": 1,
                "completed": 0,
                "skipped": 0,
            },
        )
        # error key should not be set when event has no error
        assert snap.get("error") is None

    # --- run_completed ---

    def test_run_completed_sets_status(self):
        snap = self._snap()
        update_snapshot_from_event(snap, {"event": "run_completed", "message": "Done"})
        assert snap["status"] == "completed"
        assert snap["phase"] == "completed"
        assert snap["pct"] == 100.0
        assert snap["latest_event"] == "Done"

    # --- run_failed ---

    def test_run_failed_sets_failed_status(self):
        snap = self._snap()
        update_snapshot_from_event(snap, {"event": "run_failed", "error": "crash"})
        assert snap["status"] == "failed"
        assert snap["phase"] == "failed"
        assert "crash" in snap["latest_event"]
        assert snap["error"] == "crash"

    def test_run_failed_no_error_message(self):
        snap = self._snap()
        update_snapshot_from_event(snap, {"event": "run_failed"})
        assert snap["status"] == "failed"
        assert "failed" in snap["latest_event"].lower()

    # --- log_line appended ---

    def test_log_line_appended_to_recent_logs(self):
        snap = self._snap()
        update_snapshot_from_event(snap, {"event": "run_started"}, log_line="hello")
        assert any("hello" in line for line in snap["recent_logs"])

    def test_recent_logs_capped_at_100(self):
        snap = self._snap()
        for i in range(110):
            update_snapshot_from_event(
                snap, {"event": "run_started"}, log_line=f"line {i}"
            )
        assert len(snap["recent_logs"]) <= 100

    # --- unknown event is a no-op ---

    def test_unknown_event_is_noop(self):
        snap = self._snap()
        original_status = snap["status"]
        update_snapshot_from_event(snap, {"event": "completely_unknown_event"})
        assert snap["status"] == original_status


@pytest.mark.unit
class TestSnapshotLogHandler:
    def _make_handler(self) -> tuple[SnapshotLogHandler, dict]:
        snap: dict = {"recent_logs": []}
        handler = SnapshotLogHandler(snap)
        return handler, snap

    def test_emit_appends_to_recent_logs(self):
        handler, snap = self._make_handler()
        record = logging.LogRecord(
            name="transcriptx",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )
        handler.emit(record)
        assert any("test message" in line for line in snap["recent_logs"])

    def test_emit_initialises_missing_key(self):
        snap: dict = {}  # no recent_logs key
        handler = SnapshotLogHandler(snap)
        record = logging.LogRecord(
            name="transcriptx",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="init test",
            args=(),
            exc_info=None,
        )
        handler.emit(record)
        assert "recent_logs" in snap
        assert len(snap["recent_logs"]) == 1

    def test_warning_sets_latest_event(self):
        handler, snap = self._make_handler()
        record = logging.LogRecord(
            name="transcriptx",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg="something wrong",
            args=(),
            exc_info=None,
        )
        handler.emit(record)
        assert snap.get("latest_event") == "something wrong"

    def test_info_does_not_set_latest_event(self):
        snap: dict = {"recent_logs": []}
        handler = SnapshotLogHandler(snap)
        record = logging.LogRecord(
            name="transcriptx",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="routine info",
            args=(),
            exc_info=None,
        )
        handler.emit(record)
        assert "latest_event" not in snap

    def test_logs_capped_at_100(self):
        handler, snap = self._make_handler()
        for i in range(110):
            record = logging.LogRecord(
                name="transcriptx",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg=f"msg {i}",
                args=(),
                exc_info=None,
            )
            handler.emit(record)
        assert len(snap["recent_logs"]) <= 100


@pytest.mark.unit
class TestNullProgress:
    """NullProgress satisfies ProgressCallback protocol."""

    def test_null_progress_is_progress_callback(self):
        np = NullProgress()
        assert isinstance(np, ProgressCallback)

    def test_all_methods_callable_without_error(self):
        np = NullProgress()
        np.on_stage_start("test")
        np.on_stage_progress("msg", 50.0)
        np.on_stage_complete("test")
        np.on_log("msg", level="info")
        np.on_event({"event": "run_started"})
