"""Tests for admit_and_register outcomes and registration recovery."""

from __future__ import annotations

import json
from pathlib import Path


from transcriptx.io.admit_and_register import AdmitOutcomeKind, admit_and_register
from transcriptx.io.import_metadata_sidecar import write_initial_sidecar
from transcriptx.io.managed_import_workflow import StagingCleanupPolicy
from transcriptx.io.transcript_schema import (
    SourceInfo,
    TranscriptMetadata,
    create_transcript_document,
)


def _patch(monkeypatch, transcript_root: Path, outputs: Path) -> None:
    monkeypatch.setattr(
        "transcriptx.io.managed_import_workflow.DIARISED_TRANSCRIPTS_DIR",
        transcript_root,
    )
    monkeypatch.setattr(
        "transcriptx.io.managed_import_workflow.TRANSCRIPTS_ORIGINALS_DIR",
        transcript_root / "originals",
    )
    monkeypatch.setattr(
        "transcriptx.io.admit_and_register.DIARISED_TRANSCRIPTS_DIR",
        transcript_root,
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
        "transcriptx.io.import_metadata.paths.TRANSCRIPTS_METADATA_DIR",
        transcript_root / "metadata",
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.slug_manager.INDEX_FILE",
        outputs / ".transcriptx_index.json",
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.slug_manager.OUTPUTS_DIR",
        outputs,
    )
    (transcript_root / "originals").mkdir(parents=True, exist_ok=True)
    (transcript_root / "imports").mkdir(parents=True, exist_ok=True)
    (transcript_root / "metadata").mkdir(parents=True, exist_ok=True)
    outputs.mkdir(parents=True, exist_ok=True)


def _valid_doc(original: str) -> dict:
    return create_transcript_document(
        [{"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0}],
        SourceInfo(
            type="srt",
            original_path=original,
            imported_at="2026-01-01T00:00:00+00:00",
            file_hash="abc",
            file_mtime=0.0,
        ),
        TranscriptMetadata(duration_seconds=1.0, segment_count=1, speaker_count=1),
    )


def test_admit_new_and_register(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "transcripts"
    _patch(monkeypatch, root, tmp_path / "outputs")
    staging = root / "imports" / "meeting.srt"
    staging.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")

    outcome = admit_and_register(
        staging,
        logical_basename="meeting.srt",
        staging_cleanup=StagingCleanupPolicy.APP_IMPORTS_ONLY,
        allow_provenance_backfill=False,
    )
    assert outcome.kind is AdmitOutcomeKind.IMPORTED_AND_REGISTERED
    assert outcome.slug
    assert outcome.artifact_committed
    assert outcome.registration_progressed
    assert outcome.transcript_path and outcome.transcript_path.exists()
    assert not staging.exists()


def test_registration_recovery(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "transcripts"
    _patch(monkeypatch, root, tmp_path / "outputs")
    archive = root / "originals" / "meeting.srt"
    archive.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
    target = root / "meeting.json"
    target.write_text(json.dumps(_valid_doc("originals/meeting.srt")), encoding="utf-8")
    write_initial_sidecar(
        target,
        imported_at="2026-01-01T00:00:00+00:00",
        adapter_source_id="srt",
        source_upload_basename="meeting.srt",
        archived_original_relpath="originals/meeting.srt",
    )
    staging = root / "imports" / "meeting.srt"
    staging.write_text("ignored", encoding="utf-8")

    outcome = admit_and_register(
        staging,
        logical_basename="meeting.srt",
        staging_cleanup=StagingCleanupPolicy.NEVER,
        allow_provenance_backfill=False,
    )
    assert outcome.kind is AdmitOutcomeKind.REGISTRATION_RECOVERED
    assert outcome.registration_progressed
    assert outcome.slug

    # Second call is already managed.
    again = admit_and_register(
        staging,
        logical_basename="meeting.srt",
        staging_cleanup=StagingCleanupPolicy.NEVER,
        allow_provenance_backfill=False,
    )
    assert again.kind is AdmitOutcomeKind.ALREADY_MANAGED


def test_size_limit_in_admit(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "transcripts"
    _patch(monkeypatch, root, tmp_path / "outputs")
    monkeypatch.setenv("TRANSCRIPTX_FOLDER_IMPORT_MAX_FILE_BYTES", "5")
    staging = root / "imports" / "meeting.srt"
    staging.write_text("1234567890", encoding="utf-8")
    outcome = admit_and_register(
        staging,
        logical_basename="meeting.srt",
        allow_provenance_backfill=False,
    )
    assert outcome.kind is AdmitOutcomeKind.UNSUPPORTED_OR_INVALID_INPUT
    assert "too large" in outcome.user_safe_detail.lower()


def test_unrecognized_json_is_unsupported_not_unexpected(
    monkeypatch, tmp_path: Path
) -> None:
    root = tmp_path / "transcripts"
    _patch(monkeypatch, root, tmp_path / "outputs")
    staging = root / "imports" / "foo.json"
    staging.write_text("{}", encoding="utf-8")
    outcome = admit_and_register(
        staging,
        logical_basename="foo.json",
        allow_provenance_backfill=False,
    )
    assert outcome.kind is AdmitOutcomeKind.UNSUPPORTED_OR_INVALID_INPUT
    assert outcome.artifact_committed is False
    assert "unsupported import" in outcome.user_safe_detail.lower()
    assert "unknown_input" in outcome.user_safe_detail.lower()


def test_registration_is_valid_requires_path_and_identity(
    monkeypatch, tmp_path: Path
) -> None:
    from transcriptx.core.utils import slug_manager as sm

    outputs = tmp_path / "outputs"
    outputs.mkdir()
    monkeypatch.setattr(sm, "INDEX_FILE", outputs / ".transcriptx_index.json")
    monkeypatch.setattr(sm, "OUTPUTS_DIR", outputs)

    path = tmp_path / "meeting.json"
    path.write_text("{}", encoding="utf-8")
    identity = "sha256:abc"
    sm.save_index(
        {
            "transcripts": {
                identity: {
                    "slug": "meeting",
                    "runs": [],
                    "source_basename": "meeting",
                    "source_path": str(path),
                }
            },
            "slug_to_key": {"meeting": identity},
        }
    )
    assert sm.registration_is_valid(path, identity)
    assert not sm.registration_is_valid(path, "sha256:other")
    assert not sm.registration_is_valid(tmp_path / "other.json", identity)
    # Slug alone is insufficient
    assert sm.get_slug_for_transcript(identity) == "meeting"


def test_incomplete_unrepairable_without_backfill(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "transcripts"
    _patch(monkeypatch, root, tmp_path / "outputs")
    target = root / "meeting.json"
    target.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source": {"type": "srt", "imported_at": "2026-01-01T00:00:00+00:00"},
                "segments": [
                    {"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0}
                ],
            }
        ),
        encoding="utf-8",
    )
    staging = root / "imports" / "meeting.srt"
    staging.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
    outcome = admit_and_register(
        staging,
        logical_basename="meeting.srt",
        allow_provenance_backfill=False,
    )
    assert outcome.kind is AdmitOutcomeKind.INCOMPLETE_STATE_FAILURE
    assert not outcome.artifact_committed


def test_registration_failed_then_recovered(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "transcripts"
    _patch(monkeypatch, root, tmp_path / "outputs")
    staging = root / "imports" / "meeting.srt"
    staging.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")

    calls = {"n": 0}
    real_register = __import__(
        "transcriptx.core.utils.slug_manager", fromlist=["register_transcript"]
    ).register_transcript

    def _flaky_register(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("index write failed")
        return real_register(*args, **kwargs)

    monkeypatch.setattr(
        "transcriptx.io.admit_and_register.register_transcript", _flaky_register
    )

    first = admit_and_register(
        staging,
        logical_basename="meeting.srt",
        staging_cleanup=StagingCleanupPolicy.NEVER,
        allow_provenance_backfill=False,
    )
    assert first.kind is AdmitOutcomeKind.REGISTRATION_FAILED_AFTER_ARTIFACT_COMMIT
    assert first.artifact_committed
    assert first.transcript_path and first.transcript_path.exists()

    second = admit_and_register(
        staging,
        logical_basename="meeting.srt",
        staging_cleanup=StagingCleanupPolicy.NEVER,
        allow_provenance_backfill=False,
    )
    assert second.kind is AdmitOutcomeKind.REGISTRATION_RECOVERED
    assert second.registration_progressed
    assert second.slug


def test_staging_cleanup_refuses_non_imports_path(monkeypatch, tmp_path: Path) -> None:
    from transcriptx.io import managed_import_workflow as mod

    root = tmp_path / "transcripts"
    _patch(monkeypatch, root, tmp_path / "outputs")
    outside = tmp_path / "outside.srt"
    outside.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")

    result = mod.run_managed_import_workflow(
        outside,
        logical_upload_basename="outside.srt",
        overwrite=False,
        delete_staging_on_success=True,
    )
    assert result.json_path.exists()
    assert outside.exists()


def test_exclusive_create_does_not_clobber_existing(tmp_path: Path) -> None:
    from transcriptx.io.originals_archive import exclusive_create_originals_archive

    originals = tmp_path / "originals"
    originals.mkdir()
    existing = originals / "meeting.srt"
    existing.write_bytes(b"old")
    created = exclusive_create_originals_archive("meeting.srt", originals, b"new")
    assert created != existing
    assert existing.read_bytes() == b"old"
    assert created.read_bytes() == b"new"
    assert created.name.startswith("meeting (")
