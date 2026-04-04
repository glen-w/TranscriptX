"""Canonical run-outcome read model fixtures."""

from __future__ import annotations

from transcriptx.core.pipeline.run_outcome_truth import (
    project_canonical_outcomes,
    status_for_module,
)


def _status_map(run_results: dict) -> dict[str, str]:
    return {
        row.module_id: row.status for row in project_canonical_outcomes(run_results)
    }


def test_minimal_success_fixture() -> None:
    run_results = {
        "modules_enabled": ["stats"],
        "modules_run": ["stats"],
        "modules_skipped": [],
        "modules_failed": [],
    }
    assert _status_map(run_results)["stats"] == "succeeded"


def test_partial_blocked_and_skipped_fixture() -> None:
    run_results = {
        "modules_enabled": ["emotion", "contagion", "wordclouds"],
        "modules_run": ["emotion"],
        "modules_skipped": [
            {
                "module": "contagion",
                "reason": "missing dependency",
                "execution_status": "blocked",
            },
            {
                "module": "wordclouds",
                "reason": "preset excluded",
                "execution_status": "skipped",
            },
        ],
        "modules_failed": [],
    }
    statuses = _status_map(run_results)
    assert statuses["emotion"] == "succeeded"
    assert statuses["contagion"] == "blocked"
    assert statuses["wordclouds"] == "skipped"


def test_failed_module_fixture() -> None:
    run_results = {
        "modules_enabled": ["topic_modeling"],
        "modules_run": [],
        "modules_skipped": [],
        "modules_failed": ["topic_modeling"],
    }
    assert status_for_module("topic_modeling", run_results) == "failed"


def test_cache_hit_fixture_marks_satisfied_without_fresh_execution() -> None:
    run_results = {
        "modules_enabled": ["sentiment"],
        "modules_run": ["sentiment"],
        "modules_skipped": [],
        "modules_failed": [],
        "module_outcomes": [{"module_id": "sentiment", "used_cache": True}],
    }
    rows = {row.module_id: row for row in project_canonical_outcomes(run_results)}
    assert rows["sentiment"].status == "succeeded"
    assert rows["sentiment"].used_cache is True
    assert rows["sentiment"].reason == "cache_hit"


def test_manifest_fallback_like_partial_run_results_fixture() -> None:
    # run_results exists but is partial; enabled-only module stays enabled,
    # not silently promoted to succeeded/failed.
    run_results = {
        "modules_enabled": ["stats", "sentiment"],
        "modules_run": ["stats"],
        "modules_skipped": [],
        "modules_failed": [],
    }
    statuses = _status_map(run_results)
    assert statuses["stats"] == "succeeded"
    assert statuses["sentiment"] == "enabled"
