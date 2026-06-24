"""Integration: whispermlx-style JSON through managed import."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from transcriptx.io.managed_import_workflow import run_managed_import_workflow


@pytest.mark.integration
def test_whisperx_fixture_passes_managed_import(tmp_path: Path):
    fixture = (
        Path(__file__).parent.parent
        / "fixtures"
        / "transcripts"
        / "whisperx"
        / "standard.json"
    )
    if not fixture.is_file():
        pytest.skip("fixture missing")
    staging = tmp_path / "standard.json"
    shutil.copy(fixture, staging)
    result = run_managed_import_workflow(staging, overwrite=False)
    assert result.json_path.exists()
