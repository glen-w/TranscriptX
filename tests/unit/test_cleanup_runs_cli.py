"""Smoke tests for transcriptx cleanup-runs CLI."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.unit
def test_cleanup_runs_dry_run(monkeypatch, tmp_path: Path, capsys) -> None:
    from transcriptx import cleanup_runs as mod
    from transcriptx.web.services.run_cleanup import CleanupMode, CleanupStatus

    preview = SimpleNamespace(
        plan_id="abc",
        run_count=2,
        file_count=10,
        size_estimate_bytes=100,
        transcript_subjects=1,
        group_subjects=0,
        retained=(object(),),
        warnings=(),
        blocking_errors=(),
        can_execute=True,
    )

    class FakeSvc:
        def preview_cleanup(self, mode, session_id, *, retain_policy=None):
            assert mode is CleanupMode.DELETE_OLD
            assert retain_policy is not None
            assert retain_policy.keep_human_readable
            assert retain_policy.keep_llm_summaries
            return "handle", preview

        def execute_cleanup(self, *args, **kwargs):
            raise AssertionError("execute must not run on dry-run")

    monkeypatch.setattr(mod, "RunCleanupService", FakeSvc)
    monkeypatch.setattr("transcriptx._bootstrap.bootstrap", lambda: None)
    rc = mod.main(
        [
            "--mode",
            "delete-old",
            "--keep-human-readable",
            "--keep-llm-summaries",
            "--dry-run",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "dry-run" in out
    assert "candidates: 2" in out


@pytest.mark.unit
def test_cleanup_runs_requires_yes(monkeypatch, capsys) -> None:
    from transcriptx import cleanup_runs as mod
    from transcriptx.web.services.run_cleanup import CleanupMode

    preview = SimpleNamespace(
        plan_id="abc",
        run_count=1,
        file_count=1,
        size_estimate_bytes=1,
        transcript_subjects=1,
        group_subjects=0,
        retained=(),
        warnings=(),
        blocking_errors=(),
        can_execute=True,
    )

    class FakeSvc:
        def preview_cleanup(self, mode, session_id, *, retain_policy=None):
            assert mode is CleanupMode.DELETE_OLD
            return "handle", preview

    monkeypatch.setattr(mod, "RunCleanupService", FakeSvc)
    monkeypatch.setattr("transcriptx._bootstrap.bootstrap", lambda: None)
    monkeypatch.delenv("TRANSCRIPTX_CLEANUP_YES", raising=False)
    rc = mod.main(["--mode", "delete-old"])
    assert rc == 2
    assert "refusing live delete" in capsys.readouterr().err


@pytest.mark.unit
def test_cleanup_runs_yes_executes(monkeypatch, capsys) -> None:
    from transcriptx import cleanup_runs as mod
    from transcriptx.web.services.run_cleanup import CleanupMode, CleanupStatus

    preview = SimpleNamespace(
        plan_id="abc",
        run_count=1,
        file_count=1,
        size_estimate_bytes=1,
        transcript_subjects=1,
        group_subjects=0,
        retained=(),
        warnings=(),
        blocking_errors=(),
        can_execute=True,
    )
    executed: list = []

    class FakeSvc:
        def preview_cleanup(self, mode, session_id, *, retain_policy=None):
            return "handle", preview

        def execute_cleanup(self, handle, auth, session_id):
            executed.append((handle, auth.plan_id, auth.mode))
            return SimpleNamespace(
                status=CleanupStatus.SUCCESS,
                visible_removed_count=1,
                physically_deleted_count=1,
                operation_id="op1",
                warnings=(),
                errors=(),
            )

    monkeypatch.setattr(mod, "RunCleanupService", FakeSvc)
    monkeypatch.setattr("transcriptx._bootstrap.bootstrap", lambda: None)
    rc = mod.main(["--mode", "delete-old", "--yes"])
    assert rc == 0
    assert executed
    assert executed[0][2] is CleanupMode.DELETE_OLD
    assert "SUCCESS" in capsys.readouterr().out
