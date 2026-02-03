"""
Contract tests for run manifest outputs (offline + deterministic).
"""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.core.pipeline.manifest_builder import build_output_manifest

from tests.contracts.normalization import normalize_manifest


def test_output_manifest_snapshot(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    (run_dir / ".transcriptx").mkdir(parents=True)
    (run_dir / "stats" / "data" / "global").mkdir(parents=True)
    (run_dir / "stats" / "charts" / "global" / "static").mkdir(parents=True)

    # Minimal config snapshot for manifest metadata
    config_payload = {"schema_version": 1, "config": {}}
    (run_dir / ".transcriptx" / "run_config_effective.json").write_text(
        json.dumps(config_payload)
    )

    # Minimal artifacts
    (run_dir / "stats" / "data" / "global" / "demo.json").write_text(
        json.dumps({"ok": True})
    )
    (run_dir / "stats" / "data" / "global" / "demo.csv").write_text("a,b\n1,2\n")
    (run_dir / "stats" / "charts" / "global" / "static" / "demo.png").write_bytes(
        b"png"
    )

    manifest = build_output_manifest(
        run_dir=run_dir,
        run_id="run-1",
        transcript_key="transcript-key",
        modules_enabled=["stats"],
    )
    normalized = normalize_manifest(manifest)

    golden_path = Path(__file__).resolve().parent / "goldens" / "manifest.json"
    golden = json.loads(golden_path.read_text())

    assert normalized == golden
