"""Tests for transcript picker analysis-coverage status."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.core.utils.analysis_picker_status import (
    ANALYSIS_STATUS_COMPLETE,
    ANALYSIS_STATUS_NONE,
    ANALYSIS_STATUS_PARTIAL,
    AnalysisPickerStatusIndex,
    analysis_status_by_slug,
    build_analysis_picker_status,
    format_with_analysis_status,
    is_complete_analysis_run,
    path_to_slug_from_entries,
    run_execution_status,
)


def _payload(
    *,
    preset: str | None,
    enabled: list[str] | None = None,
    ran: list[str] | None = None,
    failed: list[str] | None = None,
    skipped: list[dict] | None = None,
) -> dict:
    enabled = enabled if enabled is not None else ["stats"]
    ran = ran if ran is not None else list(enabled)
    return {
        "modules_enabled": enabled,
        "modules_run": ran,
        "modules_failed": failed or [],
        "modules_skipped": skipped or [],
        "errors": [],
        "analysis_preset": preset,
    }


def _write_run(outputs: Path, slug: str, run_id: str, payload: dict) -> None:
    run_dir = outputs / slug / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_results.json").write_text(json.dumps(payload), encoding="utf-8")


def test_format_with_analysis_status() -> None:
    assert (
        format_with_analysis_status("Meeting", ANALYSIS_STATUS_NONE)
        == "Meeting (no analysis)"
    )
    assert (
        format_with_analysis_status("Meeting", ANALYSIS_STATUS_PARTIAL)
        == "Meeting (partial analysis)"
    )
    assert (
        format_with_analysis_status("Meeting", ANALYSIS_STATUS_COMPLETE)
        == "Meeting (analysis complete)"
    )


def test_complete_analysis_run_requires_thorough_and_completed() -> None:
    assert is_complete_analysis_run(_payload(preset="thorough"))
    assert not is_complete_analysis_run(_payload(preset="quick"))
    assert not is_complete_analysis_run(_payload(preset="balanced"))
    assert not is_complete_analysis_run(
        _payload(preset="thorough", ran=["stats"], enabled=["stats", "sentiment"])
    )
    assert not is_complete_analysis_run(
        _payload(preset="thorough", ran=[], failed=["stats"])
    )


def test_run_execution_status_buckets() -> None:
    assert run_execution_status(_payload(preset="quick")) == "completed"
    assert (
        run_execution_status(
            _payload(preset="quick", ran=["stats"], enabled=["stats", "sentiment"])
        )
        == "partial"
    )
    assert (
        run_execution_status(_payload(preset="quick", ran=[], failed=["stats"]))
        == "failed"
    )


def test_analysis_status_by_slug_none_partial_complete(tmp_path: Path) -> None:
    _write_run(tmp_path, "done", "run1", _payload(preset="thorough"))
    _write_run(tmp_path, "quick", "run1", _payload(preset="quick"))
    _write_run(
        tmp_path,
        "unfinished",
        "run1",
        _payload(preset="thorough", ran=["stats"], enabled=["stats", "sentiment"]),
    )
    run_dir = tmp_path / "artifacts-only" / "run1"
    run_dir.mkdir(parents=True)

    statuses = analysis_status_by_slug(
        [
            "done/run1",
            "quick/run1",
            "unfinished/run1",
            "artifacts-only/run1",
        ],
        outputs_dir=tmp_path,
    )
    assert statuses["done"] == ANALYSIS_STATUS_COMPLETE
    assert statuses["quick"] == ANALYSIS_STATUS_PARTIAL
    assert statuses["unfinished"] == ANALYSIS_STATUS_PARTIAL
    assert statuses["artifacts-only"] == ANALYSIS_STATUS_PARTIAL
    assert "missing" not in statuses


def test_any_complete_thorough_run_marks_slug_complete(tmp_path: Path) -> None:
    _write_run(tmp_path, "mixed", "run-quick", _payload(preset="quick"))
    _write_run(tmp_path, "mixed", "run-full", _payload(preset="thorough"))
    statuses = analysis_status_by_slug(
        ["mixed/run-quick", "mixed/run-full"],
        outputs_dir=tmp_path,
    )
    assert statuses["mixed"] == ANALYSIS_STATUS_COMPLETE


def test_status_index_looks_up_path_and_defaults_to_none(tmp_path: Path) -> None:
    source = tmp_path / "meeting.json"
    source.write_text("{}", encoding="utf-8")
    index = build_analysis_picker_status(
        [],
        outputs_dir=tmp_path,
        transcripts=[
            {
                "slug": "meeting",
                "source_path": str(source),
            }
        ],
    )
    assert index.status_for(slug="meeting") == ANALYSIS_STATUS_NONE
    assert index.status_for(path=source) == ANALYSIS_STATUS_NONE
    assert index.status_for(path=str(source)) == ANALYSIS_STATUS_NONE

    populated = AnalysisPickerStatusIndex(
        by_slug={"meeting": ANALYSIS_STATUS_PARTIAL},
        path_to_slug=path_to_slug_from_entries(
            [{"slug": "meeting", "source_path": str(source)}]
        ),
    )
    assert populated.status_for(path=source) == ANALYSIS_STATUS_PARTIAL
    assert populated.status_for(slug="other") == ANALYSIS_STATUS_NONE
