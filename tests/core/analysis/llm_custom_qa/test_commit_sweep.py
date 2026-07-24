"""Tests for empty-run orphan sweep keep_generation_id fix."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.analysis.llm_custom_qa.commit import (
    commit_llm_custom_qa_artifacts,
    read_active_generation_id,
    sweep_orphan_staging,
)


@pytest.mark.unit
def test_sweep_preserves_active_commit_marker(tmp_path: Path) -> None:
    stem = tmp_path / "demo_llm_custom_qa"
    payload = {"ok": True}
    gid = commit_llm_custom_qa_artifacts(
        stem=stem,
        json_final=Path(f"{stem}.json"),
        md_final=Path(f"{stem}.md"),
        payload=payload,
        markdown="# hi\n",
        force_protocol="alias",
    )
    assert read_active_generation_id(stem) == gid
    marker = Path(f"{stem}.commit.{gid}")
    assert marker.exists()

    # Create an orphan commit marker
    orphan = Path(f"{stem}.commit.00000000-0000-0000-0000-000000000000")
    orphan.write_text("{}", encoding="utf-8")

    removed = sweep_orphan_staging(stem, keep_generation_id=gid)
    assert removed >= 1
    assert marker.exists()
    assert not orphan.exists()


@pytest.mark.unit
def test_sweep_none_still_preserves_active_pointer(tmp_path: Path) -> None:
    stem = tmp_path / "demo_llm_custom_qa"
    gid = commit_llm_custom_qa_artifacts(
        stem=stem,
        json_final=Path(f"{stem}.json"),
        md_final=Path(f"{stem}.md"),
        payload={"ok": True},
        markdown="# hi\n",
        force_protocol="alias",
    )
    # Even if caller passes None, active generation must be preserved.
    sweep_orphan_staging(stem, keep_generation_id=None)
    assert Path(f"{stem}.commit.{gid}").exists()
    assert read_active_generation_id(stem) == gid


@pytest.mark.unit
def test_v2_commit_writes_generation_named_files(tmp_path: Path) -> None:
    stem = tmp_path / "demo_llm_custom_qa"
    gid = commit_llm_custom_qa_artifacts(
        stem=stem,
        json_final=Path(f"{stem}.json"),
        md_final=Path(f"{stem}.md"),
        payload={"ok": True, "schema_id": "v2"},
        markdown="# hi\n",
        run_execution_id="run-abc",
        questions_metadata={"questions_requested": []},
        force_protocol="generational",
    )
    assert read_active_generation_id(stem) == gid
    assert Path(f"{stem}.json.{gid}").exists()
    assert Path(f"{stem}.md.{gid}").exists()
    assert Path(f"{stem}.questions_metadata.{gid}.json").exists()
    from transcriptx.core.analysis.llm_custom_qa.versioning import (
        COMMIT_MARKER_SCHEMA_VERSION,
    )

    marker = json.loads(Path(f"{stem}.commit.{gid}").read_text(encoding="utf-8"))
    assert marker["commit_marker_schema_version"] == COMMIT_MARKER_SCHEMA_VERSION
    assert marker["run_execution_id"] == "run-abc"
    # Alias best-effort
    assert Path(f"{stem}.json").exists()
