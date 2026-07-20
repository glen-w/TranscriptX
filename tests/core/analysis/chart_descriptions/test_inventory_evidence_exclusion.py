"""Inventory must not treat evidence sidecars as chart representations."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.core.analysis.chart_descriptions.inventory_builder import (
    build_logical_chart_inventory,
)


def test_inventory_skips_evidence_json_as_chart_unit(tmp_path: Path) -> None:
    run = tmp_path / "run"
    charts = run / "sentiment" / "charts" / "global" / "static"
    charts.mkdir(parents=True)
    png = charts / "rolling.png"
    ev = charts / "rolling.evidence.json"
    png.write_bytes(b"png")
    ev.write_text(
        json.dumps({"schema_id": "transcriptx.chart_evidence.v1"}), encoding="utf-8"
    )
    meta_dir = run / ".transcriptx"
    meta_dir.mkdir(parents=True)
    (meta_dir / "artifacts_meta.json").write_text(
        json.dumps(
            {
                png.relative_to(run).as_posix(): {
                    "viz_id": "sentiment.rolling_sentiment.global",
                    "module": "sentiment",
                    "scope": "global",
                    "artifact_kind": "chart",
                    "name": "rolling",
                    "format": "png",
                    "render_hint": "static",
                    "evidence_rel": ev.relative_to(run).as_posix(),
                    "evidence_sha256": "abc",
                },
                ev.relative_to(run).as_posix(): {
                    "viz_id": "sentiment.rolling_sentiment.global",
                    "module": "sentiment",
                    "scope": "global",
                    "artifact_kind": "chart_evidence",
                    "name": "rolling",
                    "format": "json",
                    "evidence_sha256": "abc",
                },
            }
        ),
        encoding="utf-8",
    )

    inventory, skips = build_logical_chart_inventory(
        run, run_kind="transcript", run_target_id="tx"
    )
    assert not skips
    assert len(inventory.charts) == 1
    chart = inventory.charts[0]
    assert chart.evidence_rel_path == ev.relative_to(run).as_posix()
    assert all(not r.rel_path.endswith(".evidence.json") for r in chart.representations)
