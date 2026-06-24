"""Integration: whispermlx-style JSON through managed import."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from transcriptx.io.managed_import_workflow import run_managed_import_workflow


def _patch_managed_dirs(monkeypatch, transcript_root: Path) -> None:
    from dataclasses import replace

    metadata_dir = transcript_root / "metadata"
    originals_dir = transcript_root / "originals"
    speaker_maps_dir = metadata_dir / "speaker_maps"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    originals_dir.mkdir(parents=True, exist_ok=True)
    speaker_maps_dir.mkdir(parents=True, exist_ok=True)
    import transcriptx.core.utils.paths as paths_mod

    monkeypatch.setattr(
        paths_mod,
        "PATHS",
        replace(
            paths_mod.PATHS,
            transcripts_dir=transcript_root,
            transcripts_metadata_dir=metadata_dir,
            transcripts_speaker_maps_dir=speaker_maps_dir,
            transcripts_originals_dir=originals_dir,
        ),
    )
    monkeypatch.setattr(
        "transcriptx.io.managed_import_workflow.DIARISED_TRANSCRIPTS_DIR",
        transcript_root,
    )
    monkeypatch.setattr(
        "transcriptx.io.managed_import_workflow.TRANSCRIPTS_ORIGINALS_DIR",
        originals_dir,
    )
    monkeypatch.setattr(
        "transcriptx.io.import_metadata_sidecar.DIARISED_TRANSCRIPTS_DIR",
        transcript_root,
    )
    monkeypatch.setattr(
        "transcriptx.io.import_metadata_sidecar.TRANSCRIPTS_METADATA_DIR",
        metadata_dir,
    )


@pytest.mark.integration
def test_whisperx_fixture_passes_managed_import(monkeypatch, tmp_path: Path) -> None:
    fixture = (
        Path(__file__).parent.parent
        / "fixtures"
        / "transcripts"
        / "whisperx"
        / "standard.json"
    )
    if not fixture.is_file():
        pytest.skip("fixture missing")

    transcript_root = tmp_path / "transcripts"
    _patch_managed_dirs(monkeypatch, transcript_root)

    staging = tmp_path / "standard.json"
    shutil.copy(fixture, staging)
    result = run_managed_import_workflow(staging, overwrite=False)
    assert result.json_path.exists()
