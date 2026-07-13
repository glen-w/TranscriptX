"""ArtifactService group-run edge cases: merge, metadata, health."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.pipeline.manifest_builder import build_output_manifest
from transcriptx.web.services.artifact_service import ArtifactService, _cached_health


def _write_member_chart(member_run: Path, run_id: str, key: str) -> None:
    chart_path = member_run / "sentiment" / "charts" / "global" / "s.png"
    chart_path.parent.mkdir(parents=True, exist_ok=True)
    chart_path.write_bytes(b"fakepng")
    manifest = build_output_manifest(
        run_dir=member_run,
        run_id=run_id,
        transcript_key=key,
        modules_enabled=["sentiment"],
    )
    (member_run / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )


@pytest.mark.unit
def test_group_run_modules_enabled_invalid_metadata(tmp_path: Path) -> None:
    run = tmp_path / "group_run"
    run.mkdir()
    assert ArtifactService._group_run_modules_enabled(run) == []

    (run / "group_run_metadata.json").write_text("{not-json", encoding="utf-8")
    assert ArtifactService._group_run_modules_enabled(run) == []

    (run / "group_run_metadata.json").write_text(
        json.dumps({"selected_modules": "sentiment"}),
        encoding="utf-8",
    )
    assert ArtifactService._group_run_modules_enabled(run) == []


@pytest.mark.unit
def test_merge_group_member_artifacts_skips_invalid_members(tmp_path: Path) -> None:
    good = tmp_path / "good_member"
    _write_member_chart(good, "run-good", "tk-good")

    group_run = tmp_path / "group_run"
    group_run.mkdir()
    (group_run / "group_member_runs.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "members": [
                    "not-a-dict",
                    {"order_index": 0, "transcript_key": "missing-dir"},
                    {
                        "order_index": 1,
                        "output_dir": str(tmp_path / "does-not-exist"),
                        "transcript_key": "gone",
                    },
                    {
                        "order_index": 2,
                        "output_dir": str(good),
                        "transcript_key": "tk-good",
                        "run_id": "run-good",
                        "transcript_path": str(tmp_path / "session_ok.json"),
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    merged = ArtifactService._merge_group_member_artifacts(group_run)
    assert len(merged) == 1
    assert merged[0].title.startswith("session_ok:")
    assert merged[0].slice_id == "member_2"


@pytest.mark.unit
def test_merge_group_member_artifacts_multi_member_order_and_ids(
    tmp_path: Path,
) -> None:
    m0 = tmp_path / "m0"
    m1 = tmp_path / "m1"
    _write_member_chart(m0, "r0", "k0")
    _write_member_chart(m1, "r1", "k1")

    group_run = tmp_path / "group_run"
    group_run.mkdir()
    (group_run / "group_member_runs.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "members": [
                    {
                        "order_index": 0,
                        "output_dir": str(m0),
                        "run_id": "r0",
                        "transcript_key": "k0",
                        "transcript_path": str(tmp_path / "alpha.json"),
                    },
                    {
                        "order_index": 1,
                        "output_dir": str(m1),
                        "run_id": "r1",
                        "transcript_key": "k1",
                        # no transcript_path → label falls back to "session"
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    merged = ArtifactService._merge_group_member_artifacts(group_run)
    assert len(merged) == 2
    ids = {a.id for a in merged}
    assert len(ids) == 2
    assert merged[0].storage_root == str(m0.resolve())
    assert merged[1].storage_root == str(m1.resolve())
    assert merged[0].title.startswith("alpha:")
    assert merged[1].title.startswith("session:")
    assert merged[0].slice_id == "member_0"
    assert merged[1].slice_id == "member_1"


@pytest.mark.unit
def test_check_run_health_group_run_missing_manifest_is_warning(
    tmp_path: Path,
) -> None:
    group_run = tmp_path / "group_run"
    group_run.mkdir()
    (group_run / "group_run_metadata.json").write_text(
        json.dumps({"schema_version": 1, "selected_modules": ["stats"]}),
        encoding="utf-8",
    )
    _cached_health.clear()
    health = ArtifactService.check_run_health(group_run)
    assert health["status"] == "warning"
    assert health["errors"] == []
    assert any("manifest" in w.lower() for w in health["warnings"])  # type: ignore[union-attr]


@pytest.mark.unit
def test_get_artifact_bytes_resolves_member_storage_root(tmp_path: Path) -> None:
    member_run = tmp_path / "member_run"
    _write_member_chart(member_run, "run-1", "tk1")

    group_run = tmp_path / "group_run"
    group_run.mkdir()
    (group_run / "group_member_runs.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "members": [
                    {
                        "order_index": 0,
                        "output_dir": str(member_run),
                        "run_id": "run-1",
                        "transcript_key": "tk1",
                        "transcript_path": str(tmp_path / "sess.json"),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    artifacts = ArtifactService.list_artifacts(group_run)
    charts = [a for a in artifacts if a.kind in ("chart_static", "chart_dynamic")]
    assert len(charts) == 1
    data = ArtifactService.get_artifact_bytes(group_run, charts[0].id)
    assert data == b"fakepng"
