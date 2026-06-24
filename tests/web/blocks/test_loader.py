"""Tests for ArtifactContentLoader."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.web.blocks.loader import ArtifactContentLoader
from transcriptx.web.models.artifact import Artifact


def _artifact(module: str, kind: str, rel_path: str) -> Artifact:
    return Artifact(
        id=rel_path,
        kind=kind,
        module=module,
        scope=None,
        speaker=None,
        subview=None,
        slice_id=None,
        rel_path=rel_path,
        bytes=10,
        mtime="2026-01-01T00:00:00",
        mime="application/json",
        tags=[],
    )


def test_load_json_by_suffix(tmp_path: Path) -> None:
    mod_dir = tmp_path / "summary"
    mod_dir.mkdir()
    payload = {"overview": "hello"}
    (mod_dir / "report.json").write_text(json.dumps(payload), encoding="utf-8")
    artifacts = (_artifact("summary", "data_json", "summary/report.json"),)
    loader = ArtifactContentLoader(tmp_path, artifacts)
    assert loader.load_json("summary", "_summary.json") is None
    data = loader.load_json("summary", "report.json")
    assert data == payload


def test_load_text_markdown(tmp_path: Path) -> None:
    mod_dir = tmp_path / "summary"
    mod_dir.mkdir()
    (mod_dir / "foo_summary.md").write_text("# Hi", encoding="utf-8")
    artifacts = (_artifact("summary", "data_txt", "summary/foo_summary.md"),)
    loader = ArtifactContentLoader(tmp_path, artifacts)
    assert loader.load_text("summary", "foo_summary.md") == "# Hi"
