"""Unit coverage for export ZIP packaging against composition fixture."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from transcriptx.web.services.artifact_service import ArtifactService
from transcriptx.web.services.export_service import ExportService

pytestmark = [pytest.mark.unit]

_MINIMAL_RUN = (
    Path(__file__).resolve().parents[1] / "fixtures" / "composition" / "minimal_run"
)


def test_zip_artifacts_from_minimal_run(tmp_path: Path) -> None:
    if not _MINIMAL_RUN.is_dir():
        pytest.skip("minimal_run fixture missing")
    run_root = tmp_path / "minimal_run"
    import os
    import shutil
    import time

    shutil.copytree(_MINIMAL_RUN, run_root)
    # Snapshot trees can carry pre-1980 mtimes; zipfile rejects those.
    now = time.time()
    for path in run_root.rglob("*"):
        if path.is_file():
            os.utime(path, (now, now))

    artifacts = ArtifactService.list_artifacts(run_root)
    assert artifacts, "minimal_run should expose exportable artifacts"
    ids = [a.id for a in artifacts]
    zip_path = ExportService.zip_artifacts(run_root, ids[: min(5, len(ids))])
    assert zip_path is not None
    assert Path(zip_path).is_file()
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
    assert names
    assert any(
        n.endswith("index.html") or "summary" in n or n.endswith(".json") for n in names
    )
