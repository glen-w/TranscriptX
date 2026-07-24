"""Journey 7: Overview/status surface shows partial and failed run labels."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.web.gui_acceptance.harness import (
    assert_no_exception,
    markdown_blob,
    run_script,
    seed_failed_run,
    seed_managed_transcript,
    seed_partial_run,
)

pytestmark = [pytest.mark.gui_acceptance, pytest.mark.heavy]

_SCRIPT = Path(__file__).resolve().parent / "scripts" / "run_status_script.py"


def test_overview_shows_partial_and_failed_labels(gui_ws, monkeypatch) -> None:
    from transcriptx.web.run_health_presentation import build_run_status_summary

    base = seed_managed_transcript(gui_ws)

    partial_ws = seed_partial_run(base)
    assert partial_ws.run_root is not None
    partial_summary = build_run_status_summary(
        partial_ws.run_root,
        health={"status": "ok", "errors": [], "warnings": []},
    )
    assert partial_summary.user_facing_label == "Partial success"

    monkeypatch.setenv("TRANSCRIPTX_GUI_ACC_RUN_ROOT", str(partial_ws.run_root))
    at_partial = run_script(_SCRIPT, default_timeout=30.0)
    assert_no_exception(at_partial)
    partial_blob = markdown_blob(at_partial)
    assert "Overview" in partial_blob
    assert "Partial success" in partial_blob

    failed_ws = seed_failed_run(base)
    assert failed_ws.run_root is not None
    failed_summary = build_run_status_summary(
        failed_ws.run_root,
        health={"status": "ok", "errors": [], "warnings": []},
    )
    assert "failed" in failed_summary.user_facing_label.lower() or (
        "issue" in failed_summary.user_facing_label.lower()
    )

    monkeypatch.setenv("TRANSCRIPTX_GUI_ACC_RUN_ROOT", str(failed_ws.run_root))
    at_failed = run_script(_SCRIPT, default_timeout=30.0)
    assert_no_exception(at_failed)
    failed_blob = markdown_blob(at_failed)
    assert "Overview" in failed_blob
    assert failed_summary.user_facing_label in failed_blob
