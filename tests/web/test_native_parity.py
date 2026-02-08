"""
Native parity test for transcript vs group artifacts.
"""

from __future__ import annotations

from pathlib import Path
import json

from transcriptx.core.pipeline.manifest_builder import build_output_manifest
from transcriptx.web.services import ArtifactService


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_manifest(run_dir: Path, run_id: str, transcript_key: str) -> None:
    manifest = build_output_manifest(
        run_dir=run_dir,
        run_id=run_id,
        transcript_key=transcript_key,
        modules_enabled=["sentiment"],
    )
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )


def test_native_parity_artifacts(tmp_path: Path) -> None:
    transcript_run = tmp_path / "transcript_run"
    _write_text(
        transcript_run / "sentiment" / "charts" / "global" / "sentiment.png",
        "PNGDATA",
    )
    _write_text(
        transcript_run / "sentiment" / "data" / "global" / "sentiment.csv",
        "score\n0.1\n-0.2\n",
    )
    _write_manifest(transcript_run, "run-1", "transcript-key")

    group_run = tmp_path / "group_run"
    _write_text(
        group_run / "combined" / "stats_group_summary.json",
        '{"summary": true}',
    )
    _write_text(
        group_run / "by_session" / "session-1" / "ner.csv",
        "entity,count\nalpha,1\n",
    )
    _write_text(
        group_run / "comparisons" / "notes.txt",
        "comparison notes",
    )
    _write_manifest(group_run, "run-2", "group-key")

    transcript_artifacts = ArtifactService.list_artifacts(transcript_run)
    group_artifacts = ArtifactService.list_artifacts(group_run)

    assert transcript_artifacts
    assert group_artifacts

    for artifact in transcript_artifacts + group_artifacts:
        assert artifact.id
        assert artifact.kind
        assert artifact.rel_path
        assert artifact.mime

    def _has_chart(artifacts):
        return any(a.kind.startswith("chart") for a in artifacts)

    def _has_table_or_text(artifacts):
        return any(a.kind in {"data_csv", "data_txt", "data_json"} for a in artifacts)

    assert _has_chart(transcript_artifacts)
    assert _has_table_or_text(transcript_artifacts)
    assert _has_table_or_text(group_artifacts)

    assert any(a.subview for a in group_artifacts)
