"""Unit tests for the global analysis progress chip helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.web.components import global_analysis_progress as gap


@pytest.mark.unit
def test_is_analysis_operation_active_single_and_batch() -> None:
    assert gap.is_analysis_operation_active({}) is False
    assert gap.is_analysis_operation_active({"analysis_run_in_progress": True}) is True
    assert (
        gap.is_analysis_operation_active(
            {"batch_ops_pending_launch": {"execute": True}}
        )
        is True
    )
    assert (
        gap.is_analysis_operation_active(
            {"batch_ops_pending_launch": {"execute": False}}
        )
        is False
    )


@pytest.mark.unit
def test_resolve_and_sync_active_target() -> None:
    state: dict = {
        "analysis_run_in_progress": True,
        "run_analysis_pending_launch": {"target_type": "Group"},
        "run_analysis_target": "Batch",
    }
    assert gap.resolve_active_analysis_target(state) == "Group"
    assert gap.sync_run_analysis_target_to_active_operation(state) == "Group"
    assert state["run_analysis_target"] == "Group"

    batch_state: dict = {
        "batch_ops_pending_launch": {"execute": True},
        "run_analysis_target": "Transcript",
    }
    assert gap.resolve_active_analysis_target(batch_state) == "Batch"
    gap.sync_run_analysis_target_to_active_operation(batch_state)
    assert batch_state["run_analysis_target"] == "Batch"


@pytest.mark.unit
def test_snapshot_summary_prefers_item_and_counts() -> None:
    title, pct, detail = gap._snapshot_summary(
        {
            "phase": "running_pipeline",
            "status": "running",
            "pct": 40.0,
            "current_item": "t1.json",
            "current_module": "stats",
            "completed": 2,
            "skipped": 0,
            "failed": 0,
            "total": 5,
        }
    )
    assert title == "Running…"
    assert pct == 40.0
    assert "t1.json" in detail
    assert "stats" in detail
    assert "2/5" in detail


@pytest.mark.unit
def test_app_shell_mounts_global_progress() -> None:
    from transcriptx.web import app as app_mod
    from transcriptx.web import shell as shell_mod

    app_source = Path(app_mod.__file__).read_text(encoding="utf-8")
    shell_source = Path(shell_mod.__file__).read_text(encoding="utf-8")
    assert "render_global_analysis_progress" in app_source
    assert "tx-global-run-progress" in shell_source
    assert "z-index: 1100" in shell_source


@pytest.mark.unit
def test_run_analysis_resumes_before_batch_branch() -> None:
    """In-progress single/group runs must win over Target=Batch."""
    import transcriptx.web.page_modules.run_analysis as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    sync_idx = source.index("sync_run_analysis_target_to_active_operation")
    pending_idx = source.index("_render_active_single_or_group_run(pending)")
    batch_idx = source.index('if target_type == "Batch":')
    assert sync_idx < pending_idx < batch_idx
    assert "disabled=operation_active" in source
