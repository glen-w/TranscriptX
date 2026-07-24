"""Contract tests for speaker-map → profile backfill."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from transcriptx.core.speaker_profiles.identity import link_file_key
from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver
from transcriptx.core.speaker_profiles.service import SpeakerProfileService
from transcriptx.io.import_metadata_sidecar import write_initial_sidecar
from transcriptx.io.transcript_schema import (
    SourceInfo,
    TranscriptMetadata,
    create_transcript_document,
)
from transcriptx.services.speaker_profiles.backfill_from_maps import (
    apply_backfill_plan,
    plan_backfill_from_maps,
)
from transcriptx.services.speaker_studio import SpeakerMappingService

IMPORT_A = "550e8400-e29b-41d4-a716-446655440000"
IMPORT_B = "660e8400-e29b-41d4-a716-446655440001"


def _patch_roots(monkeypatch: pytest.MonkeyPatch, transcripts_root: Path) -> None:
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
    (transcripts_root / archive_rel).write_text("x", encoding="utf-8")
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
            file_hash="abc",
            file_mtime=0.0,
        ),
        TranscriptMetadata(
            duration_seconds=2.0, segment_count=len(segs), speaker_count=2
        ),
    )
    path = transcripts_root / f"{name}.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    write_initial_sidecar(
        path,
        import_id=import_id,
        imported_at="2026-01-15T10:00:00+00:00",
        adapter_source_id="srt",
        source_upload_basename=f"{name}.srt",
        archived_original_relpath=archive_rel,
    )
    return path


def _service(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, transcripts_root: Path
) -> SpeakerProfileService:
    profiles_root = tmp_path / "speaker_profiles"
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    profiles_root.mkdir(parents=True, exist_ok=True)
    resolver = ManagedTranscriptResolver(
        transcripts_dir=transcripts_root, discovery_root=transcripts_root
    )
    return SpeakerProfileService(
        root=profiles_root, state_dir=state_dir, resolver=resolver
    )


@pytest.mark.unit
def test_backfill_merges_same_display_name_across_transcripts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    _patch_roots(monkeypatch, transcripts)
    a = _write_managed(transcripts, name="meeting_a", import_id=IMPORT_A)
    b = _write_managed(transcripts, name="meeting_b", import_id=IMPORT_B)
    maps = SpeakerMappingService()
    maps.bulk_update(str(a), {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"}, [])
    maps.bulk_update(str(b), {"SPEAKER_00": "Alice", "SPEAKER_01": "Carol"}, [])

    svc = _service(tmp_path, monkeypatch, transcripts)
    plan = plan_backfill_from_maps(
        service=svc,
        transcript_paths=[a, b],
        merge_by_name=True,
    )
    actions = {
        (i.transcript_path.name, i.local_speaker_key): i.action for i in plan.items
    }
    assert actions[("meeting_a.json", "SPEAKER_00")] == "create"
    assert actions[("meeting_a.json", "SPEAKER_01")] == "create"
    assert actions[("meeting_b.json", "SPEAKER_00")] == "link"
    assert actions[("meeting_b.json", "SPEAKER_01")] == "create"

    applied = apply_backfill_plan(plan, service=svc)
    assert not applied.errors
    assert len(applied.applied) == 4

    link_a = svc.get_live_link(link_file_key(IMPORT_A, "SPEAKER_00"))
    link_b = svc.get_live_link(link_file_key(IMPORT_B, "SPEAKER_00"))
    assert link_a is not None and link_b is not None
    assert link_a.profile_id == link_b.profile_id


@pytest.mark.unit
def test_backfill_skips_placeholder_and_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    _patch_roots(monkeypatch, transcripts)
    path = _write_managed(transcripts, name="meeting", import_id=IMPORT_A)
    SpeakerMappingService().bulk_update(
        str(path),
        {"SPEAKER_00": "SPEAKER_00", "SPEAKER_01": "Dana"},
        ["SPEAKER_01"],
    )
    svc = _service(tmp_path, monkeypatch, transcripts)
    plan = plan_backfill_from_maps(
        service=svc, transcript_paths=[path], merge_by_name=True
    )
    by_key = {i.local_speaker_key: i.action for i in plan.items}
    assert by_key["SPEAKER_00"] == "skip_not_named"
    assert by_key["SPEAKER_01"] == "skip_ignored"


@pytest.mark.unit
def test_backfill_idempotent_when_already_linked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    _patch_roots(monkeypatch, transcripts)
    path = _write_managed(transcripts, name="meeting", import_id=IMPORT_A)
    SpeakerMappingService().bulk_update(str(path), {"SPEAKER_00": "Eve"}, [])
    svc = _service(tmp_path, monkeypatch, transcripts)
    svc.create_profile_and_link(
        operation_idempotency_key=str(uuid4()),
        display_name="Eve",
        managed_transcript_id=IMPORT_A,
        local_speaker_key="SPEAKER_00",
    )
    plan = plan_backfill_from_maps(
        service=svc, transcript_paths=[path], merge_by_name=True
    )
    named = [i for i in plan.items if i.local_speaker_key == "SPEAKER_00"]
    assert len(named) == 1
    assert named[0].action == "skip_already_linked"


@pytest.mark.unit
def test_backfill_skips_generic_excluded_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    _patch_roots(monkeypatch, transcripts)
    path = _write_managed(transcripts, name="meeting", import_id=IMPORT_A)
    SpeakerMappingService().bulk_update(
        str(path),
        {"SPEAKER_00": "audience", "SPEAKER_01": "Alice"},
        [],
    )
    svc = _service(tmp_path, monkeypatch, transcripts)
    plan = plan_backfill_from_maps(
        service=svc, transcript_paths=[path], merge_by_name=True
    )
    by_key = {i.local_speaker_key: i.action for i in plan.items}
    assert by_key["SPEAKER_00"] == "skip_excluded_name"
    assert by_key["SPEAKER_01"] == "create"


@pytest.mark.unit
def test_speakers_empty_state_uses_speaker_id_page_key() -> None:
    import transcriptx.web.page_modules.speakers as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert 'primary_action=("Speaker Identification", "Speaker ID")' in source
