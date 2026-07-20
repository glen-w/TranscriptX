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


def test_inventory_uses_evidence_rel_from_meta_without_guess(tmp_path: Path) -> None:
    """When meta has evidence_rel, inventory must use it (not only sibling guess)."""
    run = tmp_path / "run"
    charts = run / "acts" / "charts" / "global" / "static"
    charts.mkdir(parents=True)
    png = charts / "pie.png"
    # Put evidence in a non-sibling location so filesystem guess would miss it
    ev_dir = run / "acts" / "data" / "global"
    ev_dir.mkdir(parents=True)
    ev = ev_dir / "acts.pie.global.evidence.json"
    png.write_bytes(b"png")
    ev.write_text(
        json.dumps(
            {
                "schema_id": "transcriptx.chart_evidence.v1",
                "viz_id": "acts.pie.global",
                "module": "acts",
                "labels": ["a"],
                "values": [1],
            }
        ),
        encoding="utf-8",
    )
    meta_dir = run / ".transcriptx"
    meta_dir.mkdir(parents=True)
    ev_rel = ev.relative_to(run).as_posix()
    (meta_dir / "artifacts_meta.json").write_text(
        json.dumps(
            {
                png.relative_to(run).as_posix(): {
                    "viz_id": "acts.pie.global",
                    "module": "acts",
                    "scope": "global",
                    "artifact_kind": "chart",
                    "name": "pie",
                    "format": "png",
                    "render_hint": "static",
                    "evidence_rel": ev_rel,
                    "evidence_sha256": "deadbeef",
                }
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
    assert chart.evidence_rel_path == ev_rel
    assert chart.evidence_sha256 == "deadbeef"
