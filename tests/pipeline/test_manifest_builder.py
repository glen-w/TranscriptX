"""Tests for output manifest builder."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.core.pipeline.manifest_builder import build_output_manifest


def test_build_output_manifest_basic(tmp_path: Path, monkeypatch) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    module_dir = run_dir / "sentiment" / "data" / "global"
    module_dir.mkdir(parents=True)
    data_path = module_dir / "sample_sentiment_summary.json"
    data_path.write_text("{}")

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
        modules_enabled=["sentiment"],
    )

    assert manifest["schema_version"] == 1
    assert manifest["run_id"] == "run-1"
    assert manifest["run_metadata"]["transcript_key"] == "tkey"
    assert any(
        a["rel_path"].endswith("sample_sentiment_summary.json")
        for a in manifest["artifacts"]
    )


def test_manifest_is_deterministic(tmp_path: Path, monkeypatch) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "stats").mkdir()
    (run_dir / "stats" / "report.md").write_text("content")

    monkeypatch.setattr(
        "transcriptx.core.pipeline.manifest_builder.compute_module_source_hash",
        lambda module: "hash123",
    )

    first = build_output_manifest(
        run_dir=run_dir,
        run_id="run-1",
        transcript_key="tkey",
        modules_enabled=["stats"],
    )
    second = build_output_manifest(
        run_dir=run_dir,
        run_id="run-1",
        transcript_key="tkey",
        modules_enabled=["stats"],
    )
    assert first["artifacts"] == second["artifacts"]
