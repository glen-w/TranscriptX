"""Tests for pure import admission primitives and folder scan."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from transcriptx.io.import_admission import (
    AdmissionError,
    ManagedArtifactState,
    assert_within_import_size_limit,
    derive_canonical_target,
    inspect_managed_artifact_state,
    normalize_conflict_stem,
    sanitize_upload_basename,
)
from transcriptx.io.folder_import import (
    CandidateStatus,
    ScanHandle,
    eligible_candidates,
    scan_folder_for_import,
    scan_handle_still_valid,
)
from transcriptx.io.import_metadata_sidecar import write_initial_sidecar
from transcriptx.io.transcript_schema import (
    SourceInfo,
    TranscriptMetadata,
    create_transcript_document,
)


def _patch_roots(monkeypatch, transcript_root: Path) -> None:
    monkeypatch.setattr(
        "transcriptx.io.import_admission.DIARISED_TRANSCRIPTS_DIR", transcript_root
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
    (transcript_root / "metadata").mkdir(parents=True, exist_ok=True)
    (transcript_root / "originals").mkdir(parents=True, exist_ok=True)
    (transcript_root / "imports").mkdir(parents=True, exist_ok=True)


def _write_valid(path: Path, original_relpath: str) -> None:
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


def test_sanitize_and_stem_normalisation() -> None:
    assert sanitize_upload_basename(r"C:\tmp\Meet.VTT") == "Meet.VTT"
    assert normalize_conflict_stem("Meet") == normalize_conflict_stem("meet")
    with pytest.raises(AdmissionError):
        sanitize_upload_basename("../x.vtt")
    with pytest.raises(AdmissionError):
        sanitize_upload_basename("bad\x00name.vtt")
    with pytest.raises(AdmissionError):
        derive_canonical_target(".vtt")


def test_size_limit_enforced(monkeypatch) -> None:
    monkeypatch.setenv("TRANSCRIPTX_FOLDER_IMPORT_MAX_FILE_BYTES", "10")
    assert_within_import_size_limit(10)
    with pytest.raises(AdmissionError, match="too large"):
        assert_within_import_size_limit(11)


def test_inspect_partial_states(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "transcripts"
    _patch_roots(monkeypatch, root)
    target = root / "meeting.json"
    archive = root / "originals" / "meeting.srt"
    archive.write_text("1\n00:00:00,000 --> 00:00:01,000\nHi\n", encoding="utf-8")

    assert (
        inspect_managed_artifact_state(target, transcripts_dir=root).state
        is ManagedArtifactState.ABSENT
    )

    _write_valid(target, "originals/meeting.srt")
    insp = inspect_managed_artifact_state(target, transcripts_dir=root)
    assert insp.state is ManagedArtifactState.INCOMPLETE_REPAIRABLE

    write_initial_sidecar(
        target,
        imported_at="2026-01-01T00:00:00+00:00",
        adapter_source_id="srt",
        source_upload_basename="meeting.srt",
        archived_original_relpath="originals/meeting.srt",
    )
    assert (
        inspect_managed_artifact_state(target, transcripts_dir=root).state
        is ManagedArtifactState.ALREADY_MANAGED
    )

    target.unlink()
    assert (
        inspect_managed_artifact_state(target, transcripts_dir=root).state
        is ManagedArtifactState.INCONSISTENT
    )


def test_scan_rejects_managed_root_and_relative(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "transcripts"
    _patch_roots(monkeypatch, root)
    inbox = tmp_path / "inbox"
    inbox.mkdir()

    bad = scan_folder_for_import(str(root), transcripts_dir=root)
    assert bad.closed_ok is False
    assert "managed transcripts" in (bad.error or "").lower()

    rel = scan_folder_for_import("inbox", transcripts_dir=root)
    assert rel.closed_ok is False
    assert "absolute" in (rel.error or "").lower()

    ok = scan_folder_for_import(str(inbox), transcripts_dir=root)
    assert ok.closed_ok is True


def test_scan_handle_session_dict_roundtrip(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "transcripts"
    _patch_roots(monkeypatch, root)
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "a.json").write_text(
        json.dumps({"segments": [{"start": 0, "end": 1, "text": "hi"}]}),
        encoding="utf-8",
    )

    handle = scan_folder_for_import(str(inbox), transcripts_dir=root)
    assert handle.closed_ok
    restored = ScanHandle.from_session_dict(handle.to_session_dict())
    assert restored is not None
    assert restored.scan_id == handle.scan_id
    assert len(eligible_candidates(restored)) == len(eligible_candidates(handle))
    assert all(isinstance(c.status, CandidateStatus) for c in restored.candidates)
    # Legacy in-memory asdict Enum members must also reload.
    legacy = handle.to_session_dict()
    legacy["candidates"] = [
        {**c, "status": CandidateStatus(c["status"])} for c in legacy["candidates"]
    ]
    assert ScanHandle.from_session_dict(legacy) is not None


def test_scan_stem_conflict_and_case(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "transcripts"
    _patch_roots(monkeypatch, root)
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "Meeting.vtt").write_text("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHi\n")
    (inbox / "meeting.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nHi\n", encoding="utf-8"
    )
    (inbox / "other.TXT").write_text("hello", encoding="utf-8")

    handle = scan_folder_for_import(str(inbox), transcripts_dir=root)
    assert handle.closed_ok
    by_name = {c.basename: c for c in handle.candidates}
    assert by_name["Meeting.vtt"].status is CandidateStatus.STEM_CONFLICT
    assert by_name["meeting.srt"].status is CandidateStatus.STEM_CONFLICT
    assert by_name["other.TXT"].status is CandidateStatus.NEW


def test_scan_overflow_fails_closed(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "transcripts"
    _patch_roots(monkeypatch, root)
    monkeypatch.setenv("TRANSCRIPTX_FOLDER_IMPORT_MAX_CANDIDATES", "2")
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    for i in range(3):
        (inbox / f"f{i}.srt").write_text(
            "1\n00:00:00,000 --> 00:00:01,000\nHi\n", encoding="utf-8"
        )
    handle = scan_folder_for_import(str(inbox), transcripts_dir=root)
    assert handle.closed_ok is False
    assert "more than 2" in (handle.error or "")
    assert handle.candidates == ()


def test_scan_rejects_symlink(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "transcripts"
    _patch_roots(monkeypatch, root)
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    real = inbox / "real.srt"
    real.write_text("1\n00:00:00,000 --> 00:00:01,000\nHi\n", encoding="utf-8")
    link = inbox / "link.srt"
    try:
        os.symlink(real, link)
    except OSError:
        pytest.skip("symlinks unsupported")
    handle = scan_folder_for_import(str(inbox), transcripts_dir=root)
    by_name = {c.basename: c for c in handle.candidates}
    assert by_name["link.srt"].status is CandidateStatus.SYMLINK
    assert by_name["real.srt"].status is CandidateStatus.NEW


def test_handle_invalidated_on_limit_change(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "transcripts"
    _patch_roots(monkeypatch, root)
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "a.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nHi\n", encoding="utf-8"
    )
    handle = scan_folder_for_import(str(inbox), transcripts_dir=root)
    assert scan_handle_still_valid(handle, path_input=str(inbox), transcripts_dir=root)
    monkeypatch.setenv("TRANSCRIPTX_FOLDER_IMPORT_MAX_FILE_BYTES", "12345")
    assert not scan_handle_still_valid(
        handle, path_input=str(inbox), transcripts_dir=root
    )


def test_eligible_excludes_conflicts(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "transcripts"
    _patch_roots(monkeypatch, root)
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "a.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nHi\n", encoding="utf-8"
    )
    (inbox / "a.vtt").write_text("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHi\n")
    handle = scan_folder_for_import(str(inbox), transcripts_dir=root)
    assert eligible_candidates(handle) == []


def test_stem_conflict_preserves_too_large_secondary(
    monkeypatch, tmp_path: Path
) -> None:
    root = tmp_path / "transcripts"
    _patch_roots(monkeypatch, root)
    monkeypatch.setenv("TRANSCRIPTX_FOLDER_IMPORT_MAX_FILE_BYTES", "20")
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "dup.srt").write_text("tiny", encoding="utf-8")
    (inbox / "dup.vtt").write_text("x" * 50, encoding="utf-8")
    handle = scan_folder_for_import(str(inbox), transcripts_dir=root)
    by_name = {c.basename: c for c in handle.candidates}
    assert by_name["dup.srt"].status is CandidateStatus.STEM_CONFLICT
    assert by_name["dup.vtt"].status is CandidateStatus.STEM_CONFLICT
    assert "too large" in by_name["dup.vtt"].secondary_detail.lower()


def test_incomplete_unrepairable_not_new(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "transcripts"
    _patch_roots(monkeypatch, root)
    target = root / "orphan.json"
    target.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "source": {"type": "srt", "imported_at": "2026-01-01T00:00:00+00:00"},
                "segments": [
                    {"speaker": "SPEAKER_00", "text": "Hi", "start": 0.0, "end": 1.0}
                ],
            }
        ),
        encoding="utf-8",
    )
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "orphan.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nHi\n", encoding="utf-8"
    )
    handle = scan_folder_for_import(str(inbox), transcripts_dir=root)
    cand = next(c for c in handle.candidates if c.basename == "orphan.srt")
    assert cand.status is CandidateStatus.INCOMPLETE_UNREPAIRABLE
    assert cand not in eligible_candidates(handle)


def test_stale_candidate_when_file_changes(monkeypatch, tmp_path: Path) -> None:
    from transcriptx.io.admit_and_register import AdmitOutcomeKind
    from transcriptx.io.folder_import import import_folder_candidates

    root = tmp_path / "transcripts"
    _patch_roots(monkeypatch, root)
    monkeypatch.setattr(
        "transcriptx.io.folder_import.TRANSCRIPTS_IMPORTS_DIR", root / "imports"
    )
    monkeypatch.setattr(
        "transcriptx.io.admit_and_register.DIARISED_TRANSCRIPTS_DIR", root
    )
    monkeypatch.setattr(
        "transcriptx.io.managed_import_workflow.DIARISED_TRANSCRIPTS_DIR", root
    )
    monkeypatch.setattr(
        "transcriptx.io.managed_import_workflow.TRANSCRIPTS_ORIGINALS_DIR",
        root / "originals",
    )
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    path = inbox / "fresh.srt"
    path.write_text("1\n00:00:00,000 --> 00:00:01,000\nHi\n", encoding="utf-8")
    handle = scan_folder_for_import(str(inbox), transcripts_dir=root)
    assert eligible_candidates(handle)
    path.write_text("1\n00:00:00,000 --> 00:00:02,000\nChanged\n", encoding="utf-8")
    outcomes = import_folder_candidates(handle, path_input=str(inbox))
    assert outcomes
    assert outcomes[0].kind is AdmitOutcomeKind.STALE_CANDIDATE
    assert path.exists()


def test_folder_import_preserves_source_and_admits(monkeypatch, tmp_path: Path) -> None:
    from transcriptx.core.utils import slug_manager as sm
    from transcriptx.io.admit_and_register import AdmitOutcomeKind
    from transcriptx.io.folder_import import import_folder_candidates

    root = tmp_path / "transcripts"
    outputs = tmp_path / "outputs"
    _patch_roots(monkeypatch, root)
    outputs.mkdir()
    monkeypatch.setattr(sm, "INDEX_FILE", outputs / ".transcriptx_index.json")
    monkeypatch.setattr(sm, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(
        "transcriptx.io.folder_import.TRANSCRIPTS_IMPORTS_DIR", root / "imports"
    )
    monkeypatch.setattr(
        "transcriptx.io.admit_and_register.DIARISED_TRANSCRIPTS_DIR", root
    )
    monkeypatch.setattr(
        "transcriptx.io.managed_import_workflow.DIARISED_TRANSCRIPTS_DIR", root
    )
    monkeypatch.setattr(
        "transcriptx.io.managed_import_workflow.TRANSCRIPTS_ORIGINALS_DIR",
        root / "originals",
    )
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    source = inbox / "batch.srt"
    original = "1\n00:00:00,000 --> 00:00:01,000\nHello\n"
    source.write_text(original, encoding="utf-8")
    handle = scan_folder_for_import(str(inbox), transcripts_dir=root)
    outcomes = import_folder_candidates(handle, path_input=str(inbox))
    assert len(outcomes) == 1
    assert outcomes[0].kind is AdmitOutcomeKind.IMPORTED_AND_REGISTERED
    assert source.read_text(encoding="utf-8") == original
    assert (root / "batch.json").exists()


def test_handle_invalidated_on_policy_version_mismatch(
    monkeypatch, tmp_path: Path
) -> None:
    from transcriptx.io.folder_import import ScanHandle

    root = tmp_path / "transcripts"
    _patch_roots(monkeypatch, root)
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "a.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nHi\n", encoding="utf-8"
    )
    handle = scan_folder_for_import(str(inbox), transcripts_dir=root)
    mutated = ScanHandle(
        schema_version=handle.schema_version,
        admission_policy_version=handle.admission_policy_version + 1,
        resolved_folder=handle.resolved_folder,
        resolved_transcripts_root=handle.resolved_transcripts_root,
        max_file_bytes=handle.max_file_bytes,
        max_candidates=handle.max_candidates,
        scan_id=handle.scan_id,
        scanned_at=handle.scanned_at,
        closed_ok=True,
        error=None,
        candidates=handle.candidates,
    )
    assert not scan_handle_still_valid(
        mutated, path_input=str(inbox), transcripts_dir=root
    )
