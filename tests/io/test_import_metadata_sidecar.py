"""Tests for managed import metadata sidecar read/write."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.io.import_metadata_sidecar import (
    ManagedTranscriptCategory,
    sidecar_path_for_transcript,
    validate_managed_transcript,
    write_initial_sidecar,
)
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


def test_validate_managed_transcript_clean_success_has_empty_warnings(
    tmp_path: Path, monkeypatch
) -> None:
    transcript_root = tmp_path / "transcripts"
    transcript_root.mkdir(parents=True)
    metadata_dir = transcript_root / "metadata"
    originals_dir = transcript_root / "originals"
    metadata_dir.mkdir(parents=True)
    originals_dir.mkdir(parents=True)
    archive = originals_dir / "sample.srt"
    archive.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")

    transcript = transcript_root / "sample.json"
    _write_valid_transcript(transcript, "originals/sample.srt")

    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.TRANSCRIPTS_METADATA_DIR", metadata_dir
    )
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.DIARISED_TRANSCRIPTS_DIR",
        transcript_root,
    )
    write_initial_sidecar(
        transcript,
        imported_at="2026-01-01T00:00:00+00:00",
        adapter_source_id="srt",
        source_upload_basename="sample.srt",
        archived_original_relpath="originals/sample.srt",
    )

    result = validate_managed_transcript(transcript)
    assert result.ok is True
    assert result.category == ManagedTranscriptCategory.ok
    assert result.warnings == []


def test_validate_managed_transcript_missing_sidecar(
    tmp_path: Path, monkeypatch
) -> None:
    transcript_root = tmp_path / "transcripts"
    transcript_root.mkdir(parents=True)
    transcript = transcript_root / "sample.json"
    _write_valid_transcript(transcript, "originals/sample.srt")
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.TRANSCRIPTS_METADATA_DIR",
        transcript_root / "metadata",
    )
    result = validate_managed_transcript(transcript)
    assert result.ok is False
    assert result.category == ManagedTranscriptCategory.missing_sidecar


def test_validate_managed_transcript_parse_vs_schema_errors(
    tmp_path: Path, monkeypatch
) -> None:
    transcript_root = tmp_path / "transcripts"
    metadata_dir = transcript_root / "metadata"
    transcript_root.mkdir(parents=True)
    metadata_dir.mkdir(parents=True)
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.TRANSCRIPTS_METADATA_DIR", metadata_dir
    )

    malformed = transcript_root / "bad_parse.json"
    malformed.write_text("{not-json", encoding="utf-8")
    write_initial_sidecar(
        malformed,
        imported_at="2026-01-01T00:00:00+00:00",
        adapter_source_id="srt",
        source_upload_basename="bad_parse.srt",
        archived_original_relpath="originals/missing.srt",
    )
    parse_result = validate_managed_transcript(malformed)
    assert parse_result.ok is False
    assert parse_result.category == ManagedTranscriptCategory.parse_error

    invalid_schema = transcript_root / "bad_schema.json"
    invalid_schema.write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
    write_initial_sidecar(
        invalid_schema,
        imported_at="2026-01-01T00:00:00+00:00",
        adapter_source_id="srt",
        source_upload_basename="bad_schema.srt",
        archived_original_relpath="originals/missing.srt",
    )
    schema_result = validate_managed_transcript(invalid_schema)
    assert schema_result.ok is False
    assert schema_result.category == ManagedTranscriptCategory.schema_error


def test_sidecar_parse_and_filename_mismatch(tmp_path: Path, monkeypatch) -> None:
    transcript_root = tmp_path / "transcripts"
    metadata_dir = transcript_root / "metadata"
    transcript_root.mkdir(parents=True)
    metadata_dir.mkdir(parents=True)
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.TRANSCRIPTS_METADATA_DIR", metadata_dir
    )
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.DIARISED_TRANSCRIPTS_DIR",
        transcript_root,
    )

    transcript = transcript_root / "foo.json"
    _write_valid_transcript(transcript, "originals/foo.srt")
    sidecar = sidecar_path_for_transcript(transcript)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text("{bad", encoding="utf-8")
    parse_result = validate_managed_transcript(transcript)
    assert parse_result.ok is False
    assert parse_result.category == ManagedTranscriptCategory.parse_error

    write_initial_sidecar(
        transcript,
        imported_at="2026-01-01T00:00:00+00:00",
        adapter_source_id="srt",
        source_upload_basename="foo.srt",
        archived_original_relpath="originals/foo.srt",
    )
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    payload["current_json_filename"] = "bar.json"
    sidecar.write_text(json.dumps(payload), encoding="utf-8")
    mismatch = validate_managed_transcript(transcript)
    assert mismatch.ok is False
    assert mismatch.category == ManagedTranscriptCategory.filename_mismatch


def test_validate_managed_transcript_wrong_path_conflict(
    tmp_path: Path, monkeypatch
) -> None:
    transcript_root = tmp_path / "transcripts"
    metadata_dir = transcript_root / "metadata"
    originals_dir = transcript_root / "originals"
    transcript_root.mkdir(parents=True)
    metadata_dir.mkdir(parents=True)
    originals_dir.mkdir(parents=True)
    (originals_dir / "foo.srt").write_text("x", encoding="utf-8")
    (originals_dir / "bar.srt").write_text("y", encoding="utf-8")
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.TRANSCRIPTS_METADATA_DIR", metadata_dir
    )
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.DIARISED_TRANSCRIPTS_DIR",
        transcript_root,
    )

    transcript = transcript_root / "foo.json"
    _write_valid_transcript(transcript, "originals/foo.srt")
    write_initial_sidecar(
        transcript,
        imported_at="2026-01-01T00:00:00+00:00",
        adapter_source_id="srt",
        source_upload_basename="foo.srt",
        archived_original_relpath="originals/foo.srt",
    )

    rogue = metadata_dir / "rogue.import_meta.json"
    rogue_payload = {
        "schema_version": 1,
        "import_id": "rogue-id",
        "imported_at": "2026-01-01T00:00:00+00:00",
        "adapter_source_id": "srt",
        "source_upload_basename": "bar.srt",
        "archived_original_relpath": "originals/bar.srt",
        "current_json_filename": "foo.json",
        "rename_history": [],
    }
    rogue.write_text(json.dumps(rogue_payload), encoding="utf-8")

    result = validate_managed_transcript(transcript)
    assert result.ok is False
    assert result.category == ManagedTranscriptCategory.wrong_path


def test_nested_same_basename_sidecars_do_not_false_conflict(
    tmp_path: Path, monkeypatch
) -> None:
    """Item 72: foo/meeting.json and bar/meeting.json must not conflict."""
    transcript_root = tmp_path / "transcripts"
    metadata_dir = transcript_root / "metadata"
    originals_dir = transcript_root / "originals"
    (transcript_root / "foo").mkdir(parents=True)
    (transcript_root / "bar").mkdir(parents=True)
    metadata_dir.mkdir(parents=True)
    originals_dir.mkdir(parents=True)
    (originals_dir / "foo.srt").write_text("x", encoding="utf-8")
    (originals_dir / "bar.srt").write_text("y", encoding="utf-8")
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.TRANSCRIPTS_METADATA_DIR", metadata_dir
    )
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.DIARISED_TRANSCRIPTS_DIR",
        transcript_root,
    )

    t_foo = transcript_root / "foo" / "meeting.json"
    t_bar = transcript_root / "bar" / "meeting.json"
    _write_valid_transcript(t_foo, "originals/foo.srt")
    _write_valid_transcript(t_bar, "originals/bar.srt")
    write_initial_sidecar(
        t_foo,
        imported_at="2026-01-01T00:00:00+00:00",
        adapter_source_id="srt",
        source_upload_basename="foo.srt",
        archived_original_relpath="originals/foo.srt",
    )
    write_initial_sidecar(
        t_bar,
        imported_at="2026-01-01T00:00:00+00:00",
        adapter_source_id="srt",
        source_upload_basename="bar.srt",
        archived_original_relpath="originals/bar.srt",
    )

    foo_result = validate_managed_transcript(t_foo)
    bar_result = validate_managed_transcript(t_bar)
    assert foo_result.ok is True
    assert bar_result.ok is True


def test_legacy_only_validates_with_migration_warning(
    tmp_path: Path, monkeypatch
) -> None:
    transcript_root = tmp_path / "transcripts"
    metadata_dir = transcript_root / "metadata"
    originals_dir = transcript_root / "originals"
    transcript_root.mkdir(parents=True)
    metadata_dir.mkdir(parents=True)
    originals_dir.mkdir(parents=True)
    (originals_dir / "foo.srt").write_text("x", encoding="utf-8")
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.TRANSCRIPTS_METADATA_DIR", metadata_dir
    )
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.DIARISED_TRANSCRIPTS_DIR",
        transcript_root,
    )
    transcript = transcript_root / "foo.json"
    _write_valid_transcript(transcript, "originals/foo.srt")
    from transcriptx.io.import_metadata_sidecar import (
        build_initial_sidecar,
        legacy_flat_sidecar_path_for_transcript,
        write_json_atomic,
    )

    legacy = legacy_flat_sidecar_path_for_transcript(transcript)
    write_json_atomic(
        legacy,
        build_initial_sidecar(
            import_id="id",
            imported_at="2026-01-01T00:00:00+00:00",
            adapter_source_id="srt",
            source_upload_basename="foo.srt",
            archived_original_relpath="originals/foo.srt",
            current_json_filename=transcript.name,
        ),
    )
    result = validate_managed_transcript(transcript)
    assert result.ok is True
    assert any("Legacy" in w or "legacy" in w for w in result.warnings)


def test_write_initial_sidecar_uses_supplied_import_id(
    tmp_path: Path, monkeypatch
) -> None:
    transcript_root = tmp_path / "transcripts"
    metadata_dir = transcript_root / "metadata"
    transcript_root.mkdir(parents=True)
    metadata_dir.mkdir(parents=True)
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.TRANSCRIPTS_METADATA_DIR", metadata_dir
    )
    transcript = transcript_root / "sample.json"
    transcript.write_text("{}", encoding="utf-8")

    sidecar = write_initial_sidecar(
        transcript,
        import_id="import-123",
        imported_at="2026-01-01T00:00:00+00:00",
        adapter_source_id="srt",
        source_upload_basename="sample.srt",
        archived_original_relpath="originals/sample.srt",
    )
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["import_id"] == "import-123"
