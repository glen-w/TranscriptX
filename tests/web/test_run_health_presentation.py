"""Tests for RunStatusSummary presentation."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.web.run_health_presentation import (
    build_run_status_summary,
    module_outcome_state,
)


def test_healthy_storage_with_failed_llm(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    run_results = {
        "modules_enabled": ["llm_summary", "stats"],
        "modules_run": ["stats"],
        "modules_failed": ["llm_summary"],
        "modules_skipped": [],
        "module_outcomes": [
            {
                "module_id": "llm_summary",
                "error_code": "LLM_ERROR",
                "error_message": "timeout",
            }
        ],
    }
    summary = build_run_status_summary(
        run,
        health={"status": "ok", "errors": [], "warnings": []},
        run_results=run_results,
    )
    assert summary.artifact_health == "healthy"
    assert summary.execution_status == "completed_with_issues"
    assert summary.failed_count >= 1
    assert (
        "issue" in summary.user_facing_label.lower()
        or "failed" in summary.user_facing_label.lower()
    )
    assert any(d.source == "execution" for d in summary.technical_details)
    assert summary.has_execution_issues is True


def test_missing_artifacts_not_confused_with_execution(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    summary = build_run_status_summary(
        run,
        health={"status": "error", "errors": ["Manifest missing"], "warnings": []},
        run_results={
            "modules_enabled": [],
            "modules_run": [],
            "modules_failed": [],
            "modules_skipped": [],
        },
    )
    assert summary.artifact_health == "missing"
    assert summary.user_facing_label == "Artifacts incomplete"


def test_one_module_failed_label_when_artifacts_healthy(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    summary = build_run_status_summary(
        run,
        health={"status": "healthy", "errors": [], "warnings": []},
        run_results={
            "modules_enabled": ["stats", "summary"],
            "modules_run": ["stats"],
            "modules_failed": ["summary"],
            "modules_skipped": [],
            "module_outcomes": [
                {"module_id": "summary", "error_code": "X", "error_message": "boom"},
                {"module_id": "stats", "status": "succeeded"},
            ],
        },
    )
    assert summary.execution_status == "completed_with_issues"
    assert summary.user_facing_label == "1 module failed"


def test_all_modules_failed_is_run_failed(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    summary = build_run_status_summary(
        run,
        health={"status": "ok"},
        run_results={
            "modules_enabled": ["a", "b"],
            "modules_run": [],
            "modules_failed": ["a", "b"],
            "modules_skipped": [],
            "module_outcomes": [
                {"module_id": "a", "error_code": "E", "error_message": "a"},
                {"module_id": "b", "error_code": "E", "error_message": "b"},
            ],
        },
    )
    assert summary.execution_status == "failed"
    assert summary.user_facing_label in {"Run failed", "Completed with issues"}


def test_warning_health_maps_to_partial(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    summary = build_run_status_summary(
        run,
        health={"status": "warning", "errors": [], "warnings": ["orphan file"]},
        run_results={
            "modules_enabled": ["stats"],
            "modules_run": ["stats"],
            "modules_failed": [],
            "modules_skipped": [],
        },
    )
    assert summary.artifact_health == "partial"
    assert summary.user_facing_label in {
        "Artifacts partial",
        "Partial success",
        "Completed",
    }


def test_module_outcome_state_not_run_and_match(tmp_path: Path) -> None:
    assert module_outcome_state(None, "stats") == "unknown"
    run = tmp_path / "run"
    run.mkdir()
    assert module_outcome_state(run, "stats") == "not_run"

    payload = {
        "schema_version": 2,
        "modules_enabled": ["stats", "summary"],
        "modules_run": ["stats"],
        "modules_failed": ["summary"],
        "modules_skipped": [],
        "module_outcomes": [
            {"module_id": "summary", "error_code": "E", "error_message": "x"},
        ],
    }
    (run / "run_results.json").write_text(json.dumps(payload), encoding="utf-8")
    # Prefer injected payload (avoids schema loader coupling for unit test).
    assert module_outcome_state(run, "summary", run_results=payload) == "failed"
    assert module_outcome_state(run, "missing_module", run_results=payload) == "not_run"
    assert (
        module_outcome_state(
            run,
            "stats",
            run_results={
                "modules_enabled": ["stats"],
                "modules_run": ["stats"],
                "modules_failed": [],
                "modules_skipped": [],
            },
        )
        == "succeeded"
    )
    # Invalid on-disk schema → unknown
    (run / "run_results.json").write_text("{}", encoding="utf-8")
    assert module_outcome_state(run, "summary") == "unknown"
