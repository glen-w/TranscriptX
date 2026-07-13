"""RunIndex group-scope path resolution."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

import transcriptx.web.services.run_index as run_index_module
from transcriptx.core.pipeline.manifest_builder import build_output_manifest
from transcriptx.web.services.run_index import RunIndex


def _write_viewable_run(run_dir: Path, run_id: str) -> None:
    run_dir.mkdir(parents=True)
    (run_dir / "summary.txt").write_text("ok", encoding="utf-8")
    manifest = build_output_manifest(
        run_dir=run_dir,
        run_id=run_id,
        transcript_key="group",
        modules_enabled=["stats"],
    )
    artifacts = list(manifest.get("artifacts") or [])
    artifacts.append({"rel_path": "summary.txt", "type": "text"})
    manifest["artifacts"] = artifacts
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )


@pytest.mark.unit
def test_run_index_list_and_get_root_for_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    groups_root = tmp_path / "groups"
    monkeypatch.setattr(run_index_module, "GROUP_OUTPUTS_DIR", str(groups_root))
    group_uuid = "group-abc"
    newer = groups_root / group_uuid / "run_new"
    older = groups_root / group_uuid / "run_old"
    hidden = groups_root / group_uuid / ".hidden"
    empty = groups_root / group_uuid / "run_empty"
    _write_viewable_run(newer, "run_new")
    _write_viewable_run(older, "run_old")
    hidden.mkdir(parents=True)
    empty.mkdir(parents=True)
    past = time.time() - 1000
    os.utime(older, (past, past))

    scope = SimpleNamespace(scope_type="group", uuid=group_uuid)
    runs = RunIndex.list_runs(scope)
    assert [run.run_id for run in runs] == ["run_new", "run_old"]
    assert RunIndex.get_run_root(scope, "run_new") == newer


@pytest.mark.unit
def test_run_index_group_missing_base_returns_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(run_index_module, "GROUP_OUTPUTS_DIR", str(tmp_path / "groups"))
    scope = SimpleNamespace(scope_type="group", uuid="missing")
    assert RunIndex.list_runs(scope) == []
