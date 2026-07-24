"""Tests for managed import workflow."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.io.transcript_schema import (
    SourceInfo,
    TranscriptMetadata,
    create_transcript_document,
)


def _write_valid_transcript(path: Path, original_relpath: str) -> None:
    doc = create_transcript_document(
        [{"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0}],
        SourceInfo(
            type="srt",
            original_path=original_relpath,
            imported_at="2026-01-01T00:00:00+00:00",
            file_hash="abc123",
            file_mtime=0.0,
        ),
        TranscriptMetadata(duration_seconds=1.0, segment_count=1, speaker_count=1),
    )
    path.write_text(json.dumps(doc), encoding="utf-8")


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
        "transcriptx.io.import_admission.DIARISED_TRANSCRIPTS_DIR",
        transcript_root,
    )
    monkeypatch.setattr(
        "transcriptx.io.import_admission.TRANSCRIPTS_IMPORTS_DIR",
        transcript_root / "imports",
    )
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.DIARISED_TRANSCRIPTS_DIR",
        transcript_root,
    )
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.TRANSCRIPTS_METADATA_DIR", metadata_dir
    )


def test_retry_recovers_missing_sidecar_without_reimport(
    monkeypatch, tmp_path: Path
) -> None:
    from transcriptx.io import managed_import_workflow as mod

    transcript_root = tmp_path / "transcripts"
    _patch_managed_dirs(monkeypatch, transcript_root)
    archive = transcript_root / "originals" / "meeting.srt"
    archive.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
    target_json = transcript_root / "meeting.json"
    _write_valid_transcript(target_json, "originals/meeting.srt")
    staging = transcript_root / "imports" / "meeting.srt"
    staging.parent.mkdir(parents=True, exist_ok=True)
    staging.write_text("staging", encoding="utf-8")

    monkeypatch.setattr(
        mod,
        "import_transcript",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("must not reimport")
        ),
    )

    result = mod.run_managed_import_workflow(
        staging,
        overwrite=False,
        delete_staging_on_success=True,
    )

    assert result.json_path == target_json
    assert result.archived_original_relpath == "originals/meeting.srt"
    assert result.sidecar_path.exists()
    assert not staging.exists()


def test_retry_rejects_non_originals_source_path(monkeypatch, tmp_path: Path) -> None:
    from transcriptx.io import managed_import_workflow as mod

    transcript_root = tmp_path / "transcripts"
    _patch_managed_dirs(monkeypatch, transcript_root)
    target_json = transcript_root / "meeting.json"
    _write_valid_transcript(target_json, "uploads/meeting.srt")
    staging = transcript_root / "imports" / "meeting.srt"
    staging.parent.mkdir(parents=True, exist_ok=True)
    staging.write_text("staging", encoding="utf-8")

    with pytest.raises(ValueError, match="must be under originals/"):
        mod.run_managed_import_workflow(staging, overwrite=False)


def test_existing_json_and_sidecar_without_overwrite_raises(
    monkeypatch, tmp_path: Path
) -> None:
    from transcriptx.io import managed_import_workflow as mod
    from transcriptx.io.import_metadata_sidecar import write_initial_sidecar

    transcript_root = tmp_path / "transcripts"
    _patch_managed_dirs(monkeypatch, transcript_root)
    archive = transcript_root / "originals" / "meeting.srt"
    archive.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
    target_json = transcript_root / "meeting.json"
    _write_valid_transcript(target_json, "originals/meeting.srt")
    write_initial_sidecar(
        target_json,
        imported_at="2026-01-01T00:00:00+00:00",
        adapter_source_id="srt",
        source_upload_basename="meeting.srt",
        archived_original_relpath="originals/meeting.srt",
    )
    staging = transcript_root / "imports" / "meeting.srt"
    staging.parent.mkdir(parents=True, exist_ok=True)
    staging.write_text("staging", encoding="utf-8")

    with pytest.raises(FileExistsError, match="sidecar exists"):
        mod.run_managed_import_workflow(staging, overwrite=False)


def test_retry_backfills_missing_source_original_path(
    monkeypatch, tmp_path: Path
) -> None:
    from transcriptx.io import managed_import_workflow as mod

    transcript_root = tmp_path / "transcripts"
    _patch_managed_dirs(monkeypatch, transcript_root)
    target_json = transcript_root / "meeting.json"
    target_json.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source": {
                    "type": "srt",
                    "imported_at": "2026-01-01T00:00:00+00:00",
                },
                "segments": [
                    {
                        "speaker": "SPEAKER_00",
                        "text": "Hello",
                        "start": 0.0,
                        "end": 1.0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    staging = transcript_root / "imports" / "meeting.srt"
    staging.parent.mkdir(parents=True, exist_ok=True)
    staging.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")

    result = mod.run_managed_import_workflow(staging, overwrite=False)

    assert result.json_path == target_json
    assert result.archived_original_relpath.startswith("originals/meeting")
    archived_source = transcript_root / result.archived_original_relpath
    assert archived_source.exists()
    repaired = json.loads(target_json.read_text(encoding="utf-8"))
    assert repaired["source"]["original_path"] == result.archived_original_relpath


def test_retry_backfills_when_source_key_missing(monkeypatch, tmp_path: Path) -> None:
    from transcriptx.io import managed_import_workflow as mod

    transcript_root = tmp_path / "transcripts"
    _patch_managed_dirs(monkeypatch, transcript_root)
    target_json = transcript_root / "meeting.json"
    target_json.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "segments": [
                    {
                        "speaker": "SPEAKER_00",
                        "text": "Hello",
                        "start": 0.0,
                        "end": 1.0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    staging = transcript_root / "imports" / "meeting.srt"
    staging.parent.mkdir(parents=True, exist_ok=True)
    staging.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")

    result = mod.run_managed_import_workflow(staging, overwrite=False)

    assert result.json_path == target_json
    repaired = json.loads(target_json.read_text(encoding="utf-8"))
    assert repaired["source"]["type"] == "manual"
    assert repaired["source"]["original_path"] == result.archived_original_relpath


def test_retry_reimports_raw_json_missing_schema_version(
    monkeypatch, tmp_path: Path
) -> None:
    """Sidecar retry must canonicalize WhisperX-shaped JSON missing schema_version."""
    from transcriptx.io import managed_import_workflow as mod

    transcript_root = tmp_path / "transcripts"
    _patch_managed_dirs(monkeypatch, transcript_root)
    target_json = transcript_root / "meeting.json"
    raw_whisper = {
        "segments": [
            {
                "speaker": "SPEAKER_00",
                "text": "Hello",
                "start": 0.0,
                "end": 1.0,
            }
        ],
    }
    target_json.write_text(json.dumps(raw_whisper), encoding="utf-8")
    staging = transcript_root / "imports" / "meeting.json"
    staging.parent.mkdir(parents=True, exist_ok=True)
    staging.write_text(json.dumps(raw_whisper), encoding="utf-8")

    result = mod.run_managed_import_workflow(staging, overwrite=False)

    doc = json.loads(target_json.read_text(encoding="utf-8"))
    assert doc.get("schema_version") == 1
    assert isinstance(doc.get("source"), dict)
    assert doc["source"].get("original_path") == result.archived_original_relpath
    assert result.sidecar_path.exists()


def test_retry_backfills_when_source_is_legacy_string(
    monkeypatch, tmp_path: Path
) -> None:
    from transcriptx.io import managed_import_workflow as mod

    transcript_root = tmp_path / "transcripts"
    _patch_managed_dirs(monkeypatch, transcript_root)
    target_json = transcript_root / "meeting.json"
    target_json.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source": "legacy/path/to/file.srt",
                "segments": [
                    {
                        "speaker": "SPEAKER_00",
                        "text": "Hello",
                        "start": 0.0,
                        "end": 1.0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    staging = transcript_root / "imports" / "meeting.srt"
    staging.parent.mkdir(parents=True, exist_ok=True)
    staging.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")

    result = mod.run_managed_import_workflow(staging, overwrite=False)

    repaired = json.loads(target_json.read_text(encoding="utf-8"))
    assert isinstance(repaired["source"], dict)
    assert repaired["source"]["type"] == "manual"
    assert repaired["source"]["original_path"] == result.archived_original_relpath


def test_staging_in_originals_reuses_slot_without_numeric_suffix(
    monkeypatch, tmp_path: Path
) -> None:
    """Staging path equals originals slot: do not archive as 'name (1)' or lose the file."""
    from transcriptx.io import managed_import_workflow as mod

    transcript_root = tmp_path / "transcripts"
    _patch_managed_dirs(monkeypatch, transcript_root)
    staging = transcript_root / "originals" / "meeting.srt"
    staging.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")

    result = mod.run_managed_import_workflow(
        staging,
        overwrite=False,
        delete_staging_on_success=True,
    )

    assert result.json_path == transcript_root / "meeting.json"
    assert result.archived_original_relpath == "originals/meeting.srt"
    assert staging.exists()
    assert not (transcript_root / "originals" / "meeting (1).srt").exists()


def test_import_language_variant_inherits_base_speaker_map(
    monkeypatch, tmp_path: Path
) -> None:
    from transcriptx.io import managed_import_workflow as mod
    from transcriptx.io.speaker_map_resolver import SpeakerMapResolver
    from transcriptx.services.speaker_studio.mapping_service import (
        SpeakerMappingService,
    )

    transcript_root = tmp_path / "transcripts"
    _patch_managed_dirs(monkeypatch, transcript_root)
    base_json = transcript_root / "meeting.json"
    _write_valid_transcript(base_json, "originals/meeting.srt")
    SpeakerMappingService().bulk_update(
        str(base_json),
        speaker_map={"SPEAKER_00": "Alice"},
        ignored_speakers=[],
        method="batch",
    )

    staging = transcript_root / "imports" / "meeting_fr.srt"
    staging.parent.mkdir(parents=True, exist_ok=True)
    staging.write_text("1\n00:00:00,000 --> 00:00:01,000\nBonjour\n", encoding="utf-8")

    result = mod.run_managed_import_workflow(
        staging,
        logical_upload_basename="meeting_fr.srt",
        overwrite=False,
        delete_staging_on_success=True,
    )

    assert result.json_path == transcript_root / "meeting_fr.json"
    variant_state = SpeakerMapResolver().load_mapping(result.json_path)
    assert variant_state.has_sidecar is True
    assert variant_state.speaker_map["SPEAKER_00"] == "Alice"
    assert variant_state.speaker_map_source == {
        "kind": "inherited_from_base",
        "base_transcript_relpath": "meeting.json",
    }


def test_logical_upload_basename_for_imports_staging(
    monkeypatch, tmp_path: Path
) -> None:
    """UUID-prefixed staging file still yields canonical meeting.json and originals/meeting.srt."""
    from transcriptx.io import managed_import_workflow as mod

    transcript_root = tmp_path / "transcripts"
    _patch_managed_dirs(monkeypatch, transcript_root)
    staging = transcript_root / "imports" / "a1b2c3d4_meeting.srt"
    staging.parent.mkdir(parents=True, exist_ok=True)
    staging.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")

    result = mod.run_managed_import_workflow(
        staging,
        logical_upload_basename="meeting.srt",
        overwrite=False,
        delete_staging_on_success=True,
    )

    assert result.json_path == transcript_root / "meeting.json"
    assert result.archived_original_relpath == "originals/meeting.srt"
    assert not staging.exists()


class _FakeLock:
    def __init__(self, _path, timeout=30):
        self.acquired = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_extract_retry_source_relpath_validates_and_returns(tmp_path: Path) -> None:
    from transcriptx.io import managed_import_workflow as mod

    output = tmp_path / "out"
    archive = output / "originals" / "a.srt"
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_text("x", encoding="utf-8")
    doc = output / "a.json"
    doc.write_text(
        json.dumps({"source": {"original_path": "originals/a.srt"}}), encoding="utf-8"
    )

    rel = mod._extract_retry_source_original_relpath(json_path=doc, output_dir=output)
    assert rel == "originals/a.srt"


def test_extract_retry_source_relpath_rejects_unsafe(tmp_path: Path) -> None:
    from transcriptx.io import managed_import_workflow as mod

    output = tmp_path / "out"
    output.mkdir(parents=True, exist_ok=True)
    doc = output / "a.json"
    doc.write_text(
        json.dumps({"source": {"original_path": "../evil.srt"}}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="safe relative path"):
        mod._extract_retry_source_original_relpath(json_path=doc, output_dir=output)


def test_workflow_missing_staging_raises(tmp_path: Path) -> None:
    from transcriptx.io import managed_import_workflow as mod

    with pytest.raises(FileNotFoundError):
        mod.run_managed_import_workflow(tmp_path / "missing.srt")


def test_workflow_lock_not_acquired_raises(monkeypatch, tmp_path: Path) -> None:
    from transcriptx.io import managed_import_workflow as mod

    transcript_root = tmp_path / "transcripts"
    _patch_managed_dirs(monkeypatch, transcript_root)
    staging = tmp_path / "in.srt"
    staging.write_text("x", encoding="utf-8")

    class _NoLock(_FakeLock):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.acquired = False

    monkeypatch.setattr(mod, "FileLock", _NoLock)
    with pytest.raises(RuntimeError, match="Could not acquire import lock"):
        mod.run_managed_import_workflow(staging)


def test_import_failure_does_not_write_json_or_sidecar(
    monkeypatch, tmp_path: Path
) -> None:
    """Orchestration failure after archive create: roll back this-attempt originals."""
    from transcriptx.io import managed_import_workflow as mod
    from transcriptx.io.import_metadata_sidecar import sidecar_path_for_transcript

    transcript_root = tmp_path / "transcripts"
    _patch_managed_dirs(monkeypatch, transcript_root)
    staging = tmp_path / "meeting.srt"
    staging.write_text("x", encoding="utf-8")

    monkeypatch.setattr(mod, "FileLock", _FakeLock)
    monkeypatch.setattr(mod, "build_default_registry", lambda: object())
    monkeypatch.setattr(
        mod,
        "run_import_orchestration",
        lambda **_k: (_ for _ in ()).throw(ValueError("parse failed")),
    )

    with pytest.raises(ValueError, match="parse failed"):
        mod.run_managed_import_workflow(staging, overwrite=False)

    target_json = transcript_root / "meeting.json"
    assert not target_json.exists()
    assert not sidecar_path_for_transcript(target_json).exists()
    archived = list((transcript_root / "originals").glob("meeting*"))
    assert archived == []
    assert staging.exists()
