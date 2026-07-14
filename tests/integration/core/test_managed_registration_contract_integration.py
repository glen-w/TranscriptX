"""Integration tests for managed transcript registration contracts."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from transcriptx.core.utils.canonicalization import compute_transcript_identity_hash
from transcriptx.io.managed_import_workflow import run_managed_import_workflow
from transcriptx.io.transcript_loader import load_canonical_transcript

pytestmark = pytest.mark.integration_core


def _patch_managed_roots(monkeypatch: pytest.MonkeyPatch, root: Path) -> Path:
    transcripts = root / "transcripts"
    originals = transcripts / "originals"
    metadata = transcripts / "metadata"
    transcripts.mkdir(parents=True, exist_ok=True)
    originals.mkdir(parents=True, exist_ok=True)
    metadata.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        "transcriptx.io.managed_import_workflow.DIARISED_TRANSCRIPTS_DIR", transcripts
    )
    monkeypatch.setattr(
        "transcriptx.io.managed_import_workflow.TRANSCRIPTS_ORIGINALS_DIR", originals
    )
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.DIARISED_TRANSCRIPTS_DIR", transcripts
    )
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.TRANSCRIPTS_METADATA_DIR", metadata
    )
    return transcripts


def test_managed_registration_layout_and_identity_loadability(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcripts = _patch_managed_roots(monkeypatch, tmp_path)

    fixture = Path("tests/fixtures/vtt/simple.vtt")
    staging = tmp_path / "imports" / "simple.vtt"
    staging.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(fixture, staging)

    result = run_managed_import_workflow(
        staging,
        logical_upload_basename="simple.vtt",
        overwrite=False,
        delete_staging_on_success=True,
    )

    assert result.json_path.parent == transcripts
    assert result.archived_original_path.parent == transcripts / "originals"
    # Mirrored import sidecars live under metadata/imports/ (STORAGE.md).
    assert result.sidecar_path.parent == transcripts / "metadata" / "imports"

    canonical = load_canonical_transcript(str(result.json_path))
    segments = getattr(canonical, "segments", None)
    assert isinstance(segments, list) and segments

    identity = compute_transcript_identity_hash(segments)
    assert isinstance(identity, str) and len(identity) >= 16

    # Contract: persisted canonical transcript remains re-loadable and identity-stable.
    canonical_2 = load_canonical_transcript(str(result.json_path))
    segments_2 = getattr(canonical_2, "segments", None)
    assert compute_transcript_identity_hash(segments_2) == identity
