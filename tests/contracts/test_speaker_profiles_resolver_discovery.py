"""Stage 1: ManagedTranscriptResolver + occurrence discovery."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from transcriptx.core.speaker_profiles.discovery import (
    assert_occurrence_linkable,
    assert_path_eligible_for_profile_link,
    discover_occurrences_for_resolved,
)
from transcriptx.core.speaker_profiles.errors import (
    DuplicateImportIdError,
    NotManagedTranscriptError,
    SpeakerKeyCollisionError,
    UnresolvedManagedTranscriptError,
)
from transcriptx.core.speaker_profiles.fingerprint import compute_occurrence_fingerprint
from transcriptx.core.speaker_profiles.identity import (
    canonicalize_managed_transcript_id,
)
from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver
from transcriptx.io.import_metadata.persist import load_sidecar, write_json_atomic
from transcriptx.io.import_metadata_sidecar import (
    sidecar_path_for_transcript,
    write_initial_sidecar,
)
from transcriptx.io.transcript_schema import (
    SourceInfo,
    TranscriptMetadata,
    create_transcript_document,
)

IMPORT_A = "550e8400-e29b-41d4-a716-446655440000"
IMPORT_B = "660e8400-e29b-41d4-a716-446655440001"


def _patch_import_roots(
    monkeypatch: pytest.MonkeyPatch, transcripts_root: Path
) -> None:
    metadata_dir = transcripts_root / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.DIARISED_TRANSCRIPTS_DIR",
        transcripts_root,
    )
    monkeypatch.setattr(
        "transcriptx.io.import_metadata.paths.TRANSCRIPTS_METADATA_DIR",
        metadata_dir,
    )
    # file_discovery uses PATHS.transcripts_dir via DIARISED_TRANSCRIPTS_DIR alias
    monkeypatch.setattr(
        "transcriptx.core.utils.file_discovery.DIARISED_TRANSCRIPTS_DIR",
        transcripts_root,
    )


def _write_managed(
    transcripts_root: Path,
    *,
    name: str,
    import_id: str,
    segments: list[dict[str, Any]] | None = None,
) -> Path:
    originals = transcripts_root / "originals"
    originals.mkdir(parents=True, exist_ok=True)
    archive_rel = f"originals/{name}.srt"
    (transcripts_root / archive_rel).write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nHello\n",
        encoding="utf-8",
    )
    segs = segments or [
        {"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0},
        {"speaker": "SPEAKER_01", "text": "World", "start": 1.0, "end": 2.0},
    ]
    doc = create_transcript_document(
        segs,
        SourceInfo(
            type="srt",
            original_path=archive_rel,
            imported_at="2026-01-15T10:00:00+00:00",
            file_hash="abc123",
            file_mtime=0.0,
        ),
        TranscriptMetadata(
            duration_seconds=2.0,
            segment_count=len(segs),
            speaker_count=2,
        ),
    )
    transcript = transcripts_root / f"{name}.json"
    transcript.write_text(json.dumps(doc), encoding="utf-8")
    write_initial_sidecar(
        transcript,
        import_id=import_id,
        imported_at="2026-01-15T10:00:00+00:00",
        adapter_source_id="srt",
        source_upload_basename=f"{name}.srt",
        archived_original_relpath=archive_rel,
    )
    return transcript


@pytest.mark.unit
def test_resolver_maps_import_id_to_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "transcripts"
    root.mkdir()
    _patch_import_roots(monkeypatch, root)
    path = _write_managed(root, name="meeting", import_id=IMPORT_A)

    resolver = ManagedTranscriptResolver(transcripts_dir=root, discovery_root=root)
    resolved = resolver.resolve(IMPORT_A)
    assert resolved.managed_transcript_id == IMPORT_A
    assert resolved.transcript_path == path.resolve()
    assert resolved.current_relpath == "meeting.json"
    assert resolved.source_imported_at == "2026-01-15T10:00:00+00:00"


@pytest.mark.unit
def test_resolver_canonicalises_hex_import_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "transcripts"
    root.mkdir()
    _patch_import_roots(monkeypatch, root)
    _write_managed(root, name="meeting", import_id=IMPORT_A.replace("-", "").upper())

    resolver = ManagedTranscriptResolver(transcripts_dir=root, discovery_root=root)
    # Sidecar stores uppercase hex; resolver admits via UUID canonicalisation.
    resolved = resolver.resolve(IMPORT_A)
    assert resolved.managed_transcript_id == IMPORT_A


@pytest.mark.unit
def test_duplicate_import_id_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "transcripts"
    root.mkdir()
    _patch_import_roots(monkeypatch, root)
    _write_managed(root, name="a", import_id=IMPORT_A)
    _write_managed(root, name="b", import_id=IMPORT_A)

    resolver = ManagedTranscriptResolver(transcripts_dir=root, discovery_root=root)
    diag = resolver.rebuild()
    assert IMPORT_A in diag.duplicate_import_ids
    assert resolver.list_admitted() == []
    with pytest.raises(DuplicateImportIdError):
        resolver.resolve(IMPORT_A)


@pytest.mark.unit
def test_stale_current_json_filename_not_admitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "transcripts"
    root.mkdir()
    _patch_import_roots(monkeypatch, root)
    path = _write_managed(root, name="meeting", import_id=IMPORT_A)
    sidecar = sidecar_path_for_transcript(path)
    payload = load_sidecar(sidecar)
    payload["current_json_filename"] = "renamed.json"
    write_json_atomic(sidecar, payload)

    resolver = ManagedTranscriptResolver(transcripts_dir=root, discovery_root=root)
    assert resolver.list_admitted() == []
    with pytest.raises(UnresolvedManagedTranscriptError):
        resolver.resolve(IMPORT_A)
    with pytest.raises(NotManagedTranscriptError):
        resolver.resolve_path(path)


@pytest.mark.unit
def test_ad_hoc_json_rejected_for_linking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "transcripts"
    root.mkdir()
    _patch_import_roots(monkeypatch, root)
    _write_managed(root, name="managed", import_id=IMPORT_A)

    ad_hoc = tmp_path / "run_output" / "adhoc.json"
    ad_hoc.parent.mkdir(parents=True)
    ad_hoc.write_text(
        json.dumps(
            create_transcript_document(
                [{"speaker": "SPEAKER_00", "text": "x", "start": 0, "end": 1}],
                SourceInfo(
                    type="srt",
                    original_path="originals/x.srt",
                    imported_at="2026-01-01T00:00:00+00:00",
                ),
            )
        ),
        encoding="utf-8",
    )

    resolver = ManagedTranscriptResolver(transcripts_dir=root, discovery_root=root)
    assert resolver.is_managed_path(ad_hoc) is False
    with pytest.raises(NotManagedTranscriptError):
        assert_path_eligible_for_profile_link(ad_hoc, resolver)


@pytest.mark.unit
def test_occurrence_discovery_and_fingerprint_stability(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "transcripts"
    root.mkdir()
    _patch_import_roots(monkeypatch, root)
    segments = [
        {"speaker": "SPEAKER_00", "text": "hi", "start": 1, "end": 2},
        {"speaker": "SPEAKER_00", "text": "there", "start": 1.0, "end": 2.0},
        {"speaker": "SPEAKER_01", "text": "yo", "start": 3.0, "end": 4.0},
    ]
    _write_managed(root, name="meeting", import_id=IMPORT_A, segments=segments)

    resolver = ManagedTranscriptResolver(transcripts_dir=root, discovery_root=root)
    resolved = resolver.resolve(IMPORT_A)
    occs = discover_occurrences_for_resolved(resolved)
    assert {o.local_speaker_key for o in occs} == {"SPEAKER_00", "SPEAKER_01"}
    sp0 = next(o for o in occs if o.local_speaker_key == "SPEAKER_00")
    assert sp0.segment_count == 2
    assert sp0.occurrence_fingerprint == compute_occurrence_fingerprint(
        [
            {"speaker": "SPEAKER_00", "text": "hi", "start": 1, "end": 2},
            {"speaker": "SPEAKER_00", "text": "there", "start": 1.0, "end": 2.0},
        ]
    )
    # String timestamps canonicalise identically for fingerprinting.
    assert sp0.occurrence_fingerprint == compute_occurrence_fingerprint(
        [
            {"speaker": "SPEAKER_00", "text": "hi", "start": "1.0", "end": "2.0"},
            {"speaker": "SPEAKER_00", "text": "there", "start": "1.0", "end": "2.0"},
        ]
    )
    assert sp0.managed_transcript_id == canonicalize_managed_transcript_id(IMPORT_A)


@pytest.mark.unit
def test_occurrence_collision_blocks_linking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "transcripts"
    root.mkdir()
    _patch_import_roots(monkeypatch, root)
    segments = [
        {"speaker": "SPEAKER_00", "text": "a", "start": 0, "end": 1},
        {"speaker": "speaker_0", "text": "b", "start": 1, "end": 2},
        {"speaker": "0", "text": "c", "start": 2, "end": 3},
    ]
    _write_managed(root, name="meeting", import_id=IMPORT_B, segments=segments)

    resolver = ManagedTranscriptResolver(transcripts_dir=root, discovery_root=root)
    occs = discover_occurrences_for_resolved(resolver.resolve(IMPORT_B))
    assert len(occs) == 1
    assert occs[0].collision is True
    with pytest.raises(SpeakerKeyCollisionError):
        assert_occurrence_linkable(occs[0])


@pytest.mark.unit
def test_non_uuid_import_id_skipped_from_admission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "transcripts"
    root.mkdir()
    _patch_import_roots(monkeypatch, root)
    _write_managed(root, name="meeting", import_id="not-a-uuid")

    resolver = ManagedTranscriptResolver(transcripts_dir=root, discovery_root=root)
    diag = resolver.rebuild()
    assert diag.admitted_count == 0
    assert diag.skipped_non_uuid_import_id
