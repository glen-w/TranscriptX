"""Integration tests for io managed import integration."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from transcriptx.io.managed_import_workflow import run_managed_import_workflow
from transcriptx.io.import_metadata_sidecar import (
    sidecar_path_for_transcript,
    validate_managed_transcript,
)

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
        "transcriptx.io.import_admission.DIARISED_TRANSCRIPTS_DIR", transcripts
    )
    monkeypatch.setattr(
        "transcriptx.io.import_admission.TRANSCRIPTS_IMPORTS_DIR",
        transcripts / "imports",
    )
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.DIARISED_TRANSCRIPTS_DIR", transcripts
    )
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.TRANSCRIPTS_METADATA_DIR", metadata
    )
    return transcripts


def test_managed_import_vtt_happy_path_creates_canonical_and_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcripts = _patch_managed_roots(monkeypatch, tmp_path)

    fixture = Path("tests/fixtures/vtt/simple.vtt")
    staging = transcripts / "imports" / "simple.vtt"
    staging.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(fixture, staging)

    result = run_managed_import_workflow(
        staging,
        logical_upload_basename="simple.vtt",
        overwrite=False,
        delete_staging_on_success=True,
    )

    assert result.json_path.exists()
    assert result.archived_original_path.exists()
    assert result.sidecar_path == sidecar_path_for_transcript(result.json_path)
    assert not staging.exists()

    doc = json.loads(result.json_path.read_text(encoding="utf-8"))
    assert doc["schema_version"] == 1
    assert doc["source"]["original_path"] == result.archived_original_relpath
    assert isinstance(doc.get("segments"), list) and doc["segments"]

    validation = validate_managed_transcript(result.json_path)
    assert validation.ok is True
    assert validation.warnings == []

    sidecar = json.loads(result.sidecar_path.read_text(encoding="utf-8"))
    assert sidecar["current_json_filename"] == result.json_path.name
    assert sidecar["archived_original_relpath"] == result.archived_original_relpath


def test_managed_import_failure_does_not_create_json_or_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcripts = _patch_managed_roots(monkeypatch, tmp_path)

    staging = tmp_path / "imports" / "unknown.bin"
    staging.parent.mkdir(parents=True, exist_ok=True)
    staging.write_bytes(b"\x00\x01\x02")

    with pytest.raises(Exception):
        run_managed_import_workflow(staging, overwrite=False)

    assert not (transcripts / "unknown.json").exists()
    assert not (transcripts / "metadata" / "unknown.import_meta.json").exists()
