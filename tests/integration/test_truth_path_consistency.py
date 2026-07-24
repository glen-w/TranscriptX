"""Integration tests for execution truth-path consistency."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.app.controllers.run_controller import _load_manifest
from transcriptx.core.analysis.stats.report_input_resolver import resolve_report_inputs
from transcriptx.core.pipeline.manifest_loader import load_run_outcome_context
from transcriptx.core.pipeline.run_outcome_truth import project_canonical_outcomes
from transcriptx.web.blocks.session_context import (
    load_run_results_dict as _load_run_results,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_truth_path_fixture_cross_consumer_consistency(tmp_path: Path) -> None:
    """
    One fixture directory should produce consistent statuses across:
    - typed run outcome context loader
    - canonical projection
    - overview typed loader path
    - report resolver status path
    - run-controller manifest loader fallback behavior
    """
    run_dir = tmp_path / "outputs" / "slug_a" / "run_001"
    _write_json(
        run_dir / "run_results.json",
        {
            "schema_version": 1,
            "run_id": "run_001",
            "transcript_key": "tk_001",
            "modules_enabled": [
                "sentiment",
                "contagion",
                "wordclouds",
                "topic_modeling",
            ],
            "modules_run": ["sentiment"],
            "modules_skipped": [
                {
                    "module": "contagion",
                    "reason": "missing emotion",
                    "execution_status": "blocked",
                },
                {
                    "module": "wordclouds",
                    "reason": "preset exclusion",
                    "execution_status": "skipped",
                },
            ],
            "modules_failed": ["topic_modeling"],
            "errors": ["topic_modeling: model init error"],
            "module_outcomes": [
                {
                    "module_id": "sentiment",
                    "execution_status": "run",
                    "used_cache": True,
                }
            ],
        },
    )
    _write_json(
        run_dir / "manifest.json",
        {
            "manifest_type": "artifact_manifest",
            "run_id": "run_001",
            "run_metadata": {},
            "artifacts": [],
        },
    )
    _write_json(
        run_dir / ".transcriptx" / "manifest.json",
        {"manifest_type": "run_manifest", "run_id": "run_001"},
    )

    # report resolver "full_section" path for sentiment
    sentiment_dir = run_dir / "sentiment" / "data" / "global"
    sentiment_dir.mkdir(parents=True, exist_ok=True)
    (sentiment_dir / "base_sentiment_summary.json").write_text(
        json.dumps({"mean_compound": 0.42}), encoding="utf-8"
    )

    ctx = load_run_outcome_context(run_dir)
    overview_rr = _load_run_results(run_dir)
    controller_manifest = _load_manifest(run_dir)
    resolver_map, _ = resolve_report_inputs(run_dir, "base")

    assert overview_rr is not None
    assert controller_manifest is not None
    assert controller_manifest.get("manifest_type") == "artifact_manifest"
    assert ctx.run_results["run_id"] == "run_001"
    assert ctx.artifact_manifest is not None

    rows = project_canonical_outcomes(ctx.run_results)
    by_module = {row.module_id: row for row in rows}

    assert by_module["sentiment"].status == "succeeded"
    assert by_module["sentiment"].used_cache is True
    assert by_module["contagion"].status == "blocked"
    assert by_module["wordclouds"].status == "skipped"
    assert by_module["topic_modeling"].status == "failed"

    # Resolver should reflect canonical status semantics and still parse valid section input.
    assert resolver_map["sentiment"].module_status == "succeeded"
    assert resolver_map["contagion"].module_status == "blocked"
    assert resolver_map["wordclouds"].module_status == "skipped"
    assert resolver_map["topic_modeling"].module_status == "failed"
    assert resolver_map["sentiment"].parsed_data == {"mean_compound": 0.42}
