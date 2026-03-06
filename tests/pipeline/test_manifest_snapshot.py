"""Snapshot tests for output manifest paths."""

from __future__ import annotations

import json
from pathlib import Path

from pytest import MonkeyPatch

from transcriptx.core.pipeline.manifest_builder import (  # type: ignore[import]
    build_output_manifest,
)


def test_manifest_output_paths_snapshot(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    sentiment_dir = run_dir / "sentiment" / "data" / "global"
    sentiment_dir.mkdir(parents=True)
    (sentiment_dir / "sample_sentiment_summary.json").write_text("{}")

    stats_dir = run_dir / "stats"
    stats_dir.mkdir()
    (stats_dir / "report.md").write_text("# report")
    (stats_dir / "report.txt").write_text("report")

    meta_dir = run_dir / ".transcriptx"
    meta_dir.mkdir()
    (meta_dir / "run_config_effective.json").write_text(
        json.dumps({"schema_version": 1, "config": {"analysis": {"mode": "quick"}}})
    )

    monkeypatch.setattr(
        "transcriptx.core.pipeline.manifest_builder.compute_module_source_hash",
        lambda module: "hash123",
    )

    manifest = build_output_manifest(
        run_dir=run_dir,
        run_id="run-1",
        transcript_key="tkey",
        modules_enabled=["sentiment", "stats"],
    )

    expected_paths = json.loads(
        (
            Path(__file__).parent.parent / "fixtures" / "manifest_expected_paths.json"
        ).read_text(encoding="utf-8")
    )
    actual_paths = sorted(artifact["rel_path"] for artifact in manifest["artifacts"])
    assert actual_paths == expected_paths
