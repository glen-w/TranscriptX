"""Tests for overview run_results loading and canonical skip projection."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.web.blocks.session_context import (
    load_run_results_dict as _load_run_results,
)
from transcriptx.core.pipeline.run_outcome_truth import project_canonical_outcomes


def _write_run_results(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_load_run_results_uses_typed_loader(tmp_path: Path) -> None:
    run_root = tmp_path / "run1"
    run_root.mkdir(parents=True, exist_ok=True)
    _write_run_results(
        run_root / "run_results.json",
        {
            "schema_version": 2,
            "run_id": "r1",
            "transcript_key": "t1",
            "modules_enabled": ["stats"],
            "modules_run": ["stats"],
            "modules_skipped": [],
            "modules_failed": [],
            "errors": [],
        },
    )
    out = _load_run_results(run_root)
    assert out is not None
    assert out["run_id"] == "r1"
    assert out["modules_run"] == ["stats"]


def test_overview_canonical_skip_and_blocked_projection(tmp_path: Path) -> None:
    run_root = tmp_path / "run2"
    run_root.mkdir(parents=True, exist_ok=True)
    _write_run_results(
        run_root / "run_results.json",
        {
            "schema_version": 2,
            "run_id": "r2",
            "transcript_key": "t2",
            "modules_enabled": ["emotion", "contagion", "wordclouds"],
            "modules_run": ["emotion"],
            "modules_skipped": [
                {
                    "module": "contagion",
                    "reason": "deps",
                    "execution_status": "blocked",
                },
                {
                    "module": "wordclouds",
                    "reason": "preset",
                    "execution_status": "skipped",
                },
            ],
            "modules_failed": [],
            "errors": [],
        },
    )
    rr = _load_run_results(run_root)
    assert rr is not None
    outcomes = project_canonical_outcomes(rr)
    statuses = {o.module_id: o.status for o in outcomes}
    assert statuses["contagion"] == "blocked"
    assert statuses["wordclouds"] == "skipped"
