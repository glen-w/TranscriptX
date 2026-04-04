"""Group run chart discovery merges per-member transcript run outputs."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.core.pipeline.manifest_builder import build_output_manifest
from transcriptx.core.utils.artifact_writer import write_json
from transcriptx.web.services.artifact_service import ArtifactService


def test_group_charts_merge_member_runs(tmp_path: Path) -> None:
    member_run = tmp_path / "member_run"
    chart_path = member_run / "sentiment" / "charts" / "global" / "s.png"
    chart_path.parent.mkdir(parents=True, exist_ok=True)
    chart_path.write_bytes(b"fakepng")

    manifest = build_output_manifest(
        run_dir=member_run,
        run_id="run-1",
        transcript_key="tk1",
        modules_enabled=["sentiment"],
    )
    (member_run / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    group_run = tmp_path / "group_run"
    group_run.mkdir(parents=True, exist_ok=True)
    (group_run / "group_member_runs.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "members": [
                    {
                        "order_index": 0,
                        "transcript_path": str(tmp_path / "session_a.json"),
                        "transcript_key": "tk1",
                        "run_id": "run-1",
                        "output_dir": str(member_run),
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    artifacts = ArtifactService.list_artifacts(group_run)
    charts = [a for a in artifacts if a.kind in ("chart_static", "chart_dynamic")]
    assert len(charts) == 1
    assert charts[0].storage_root == str(member_run.resolve())
    assert "member_session" in charts[0].tags
    assert charts[0].title and charts[0].title.startswith("session_a:")

    base = ArtifactService._artifact_base_path(group_run, charts[0])
    resolved = ArtifactService._resolve_safe_path(base, charts[0].rel_path)
    assert resolved is not None
    assert resolved.exists()


def test_group_merge_uses_selected_modules_from_group_run_metadata(
    tmp_path: Path,
) -> None:
    """Merged member charts get produced_by when group_run_metadata lists selected_modules."""
    member_run = tmp_path / "member_run"
    chart_path = member_run / "sentiment" / "charts" / "global" / "s.png"
    chart_path.parent.mkdir(parents=True, exist_ok=True)
    chart_path.write_bytes(b"fakepng")

    manifest = build_output_manifest(
        run_dir=member_run,
        run_id="run-1",
        transcript_key="tk1",
        modules_enabled=["sentiment"],
    )
    (member_run / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    group_run = tmp_path / "group_run"
    group_run.mkdir(parents=True, exist_ok=True)
    (group_run / "group_run_metadata.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "selected_modules": ["sentiment", "stats"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (group_run / "group_member_runs.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "members": [
                    {
                        "order_index": 0,
                        "transcript_path": str(tmp_path / "session_a.json"),
                        "transcript_key": "tk1",
                        "run_id": "run-1",
                        "output_dir": str(member_run),
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    artifacts = ArtifactService.list_artifacts(group_run)
    charts = [a for a in artifacts if a.kind in ("chart_static", "chart_dynamic")]
    assert len(charts) == 1
    assert charts[0].produced_by is not None
    assert charts[0].produced_by == "sentiment" or charts[0].produced_by.startswith(
        "sentiment/"
    )


def test_group_aggregate_charts_tagged_separately_from_member_charts(
    tmp_path: Path,
) -> None:
    """Aggregate charts carry group_aggregate; merged member charts carry member_session only."""
    member_run = tmp_path / "member_run"
    m_chart = member_run / "sentiment" / "charts" / "global" / "static" / "m.png"
    m_chart.parent.mkdir(parents=True, exist_ok=True)
    m_chart.write_bytes(b"fakepng")

    manifest = build_output_manifest(
        run_dir=member_run,
        run_id="run-1",
        transcript_key="tk1",
        modules_enabled=["sentiment"],
    )
    (member_run / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    group_run = tmp_path / "group_run"
    group_run.mkdir(parents=True, exist_ok=True)
    g_chart = group_run / "acts" / "charts" / "global" / "static" / "g.png"
    g_chart.parent.mkdir(parents=True, exist_ok=True)
    g_chart.write_bytes(b"fakepng")
    meta_dir = group_run / ".transcriptx"
    meta_dir.mkdir(parents=True, exist_ok=True)
    rel = g_chart.relative_to(group_run).as_posix()
    write_json(
        meta_dir / "artifacts_meta.json",
        {
            rel: {
                "tags": ["group_aggregate"],
                "title": "Group aggregate acts",
                "scope": "global",
            }
        },
    )

    (group_run / "group_member_runs.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "members": [
                    {
                        "order_index": 0,
                        "transcript_path": str(tmp_path / "session_a.json"),
                        "transcript_key": "tk1",
                        "run_id": "run-1",
                        "output_dir": str(member_run),
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    artifacts = ArtifactService.list_artifacts(group_run)
    charts = [a for a in artifacts if a.kind in ("chart_static", "chart_dynamic")]
    assert len(charts) == 2
    member_charts = [a for a in charts if a.storage_root]
    agg_charts = [a for a in charts if not a.storage_root]
    assert len(member_charts) == 1
    assert len(agg_charts) == 1
    assert "member_session" in member_charts[0].tags
    assert "group_aggregate" not in member_charts[0].tags
    assert "group_aggregate" in agg_charts[0].tags
    assert "member_session" not in agg_charts[0].tags
