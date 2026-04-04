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
    metadata_dir = transcript_root / "metadata"
    originals_dir = transcript_root / "originals"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    originals_dir.mkdir(parents=True, exist_ok=True)
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
        "transcriptx.io.import_metadata_sidecar.TRANSCRIPTS_METADATA_DIR", metadata_dir
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
    staging = tmp_path / "imports" / "meeting.srt"
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
    staging = tmp_path / "imports" / "meeting.srt"
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
    staging = tmp_path / "imports" / "meeting.srt"
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
                "schema_version": "1.0",
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
    staging = tmp_path / "imports" / "meeting.srt"
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
                "schema_version": "1.0",
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
    staging = tmp_path / "imports" / "meeting.srt"
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
    staging = tmp_path / "imports" / "meeting.json"
    staging.parent.mkdir(parents=True, exist_ok=True)
    staging.write_text(json.dumps(raw_whisper), encoding="utf-8")

    result = mod.run_managed_import_workflow(staging, overwrite=False)

    doc = json.loads(target_json.read_text(encoding="utf-8"))
    assert doc.get("schema_version") == "1.0"
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
                "schema_version": "1.0",
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
    staging = tmp_path / "imports" / "meeting.srt"
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
    staging.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8"
    )

    result = mod.run_managed_import_workflow(
        staging,
        overwrite=False,
        delete_staging_on_success=True,
    )

    assert result.json_path == transcript_root / "meeting.json"
    assert result.archived_original_relpath == "originals/meeting.srt"
    assert staging.exists()
    assert not (transcript_root / "originals" / "meeting (1).srt").exists()


def test_logical_upload_basename_for_imports_staging(
    monkeypatch, tmp_path: Path
) -> None:
    """UUID-prefixed staging file still yields canonical meeting.json and originals/meeting.srt."""
    from transcriptx.io import managed_import_workflow as mod

    transcript_root = tmp_path / "transcripts"
    _patch_managed_dirs(monkeypatch, transcript_root)
    staging = tmp_path / "imports" / "a1b2c3d4_meeting.srt"
    staging.parent.mkdir(parents=True, exist_ok=True)
    staging.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8"
    )

    result = mod.run_managed_import_workflow(
        staging,
        logical_upload_basename="meeting.srt",
        overwrite=False,
        delete_staging_on_success=True,
    )

    assert result.json_path == transcript_root / "meeting.json"
    assert result.archived_original_relpath == "originals/meeting.srt"
    assert not staging.exists()
