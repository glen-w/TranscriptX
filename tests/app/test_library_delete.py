"""Library inspector delete: managed JSON + companions; refuse non-library paths."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.app.library_delete import (
    delete_managed_library_transcript,
    is_managed_library_transcript,
)
from transcriptx.core.utils import slug_manager


@pytest.fixture
def transcript_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    transcripts = tmp_path / "transcripts"
    metadata = transcripts / "metadata"
    readable = transcripts / "readable"
    originals = transcripts / "originals"
    for path in (transcripts, metadata, readable, originals):
        path.mkdir(parents=True)

    import transcriptx.app.library_delete as library_delete
    import transcriptx.core.audio.linked_transcripts as linked
    import transcriptx.io.import_metadata.paths as import_paths

    monkeypatch.setattr(library_delete, "DIARISED_TRANSCRIPTS_DIR", transcripts)
    monkeypatch.setattr(linked, "DIARISED_TRANSCRIPTS_DIR", transcripts)
    monkeypatch.setattr(linked, "READABLE_TRANSCRIPTS_DIR", readable)
    monkeypatch.setattr(linked, "TRANSCRIPTS_ORIGINALS_DIR", originals)
    monkeypatch.setattr(
        linked,
        "speaker_map_sidecar_candidates",
        lambda transcript: [
            Path(transcript).with_name(f"{Path(transcript).stem}.speaker_map.json")
        ],
    )
    monkeypatch.setattr(import_paths, "DIARISED_TRANSCRIPTS_DIR", transcripts)
    monkeypatch.setattr(import_paths, "TRANSCRIPTS_METADATA_DIR", metadata)

    state_file = tmp_path / "processing_state.json"
    state_file.write_text('{"processed_files": {}}', encoding="utf-8")
    monkeypatch.setattr(
        "transcriptx.core.utils.processing_state.PROCESSING_STATE_FILE", state_file
    )
    index_path = tmp_path / ".transcriptx_index.json"
    monkeypatch.setattr(slug_manager, "INDEX_FILE", index_path)
    return {
        "transcripts": transcripts,
        "readable": readable,
        "originals": originals,
        "index": index_path,
        "state_file": state_file,
    }


def test_is_managed_library_transcript_rejects_sidecars_and_outside(
    transcript_roots, tmp_path: Path
) -> None:
    transcripts = transcript_roots["transcripts"]
    json_path = transcripts / "keep.json"
    json_path.write_text("{}", encoding="utf-8")
    sidecar = transcripts / "keep.speaker_map.json"
    sidecar.write_text("{}", encoding="utf-8")
    nested = transcripts / "metadata" / "keep.json"
    nested.write_text("{}", encoding="utf-8")
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")

    assert is_managed_library_transcript(json_path)
    assert not is_managed_library_transcript(sidecar)
    assert not is_managed_library_transcript(nested)
    assert not is_managed_library_transcript(outside)


def test_delete_removes_transcript_companions_and_index(
    transcript_roots, tmp_path: Path
) -> None:
    transcripts = transcript_roots["transcripts"]
    transcript = transcripts / "session.json"
    transcript.write_text("{}", encoding="utf-8")
    sidecar = transcript.with_name("session.speaker_map.json")
    sidecar.write_text("{}", encoding="utf-8")
    readable = transcript_roots["readable"] / "session.txt"
    readable.write_text("hello", encoding="utf-8")
    recording = tmp_path / "session.mp3"
    recording.write_bytes(b"audio")
    run_dir = tmp_path / "outputs" / "session" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "run_results.json").write_text("{}", encoding="utf-8")

    slug_manager.register_transcript(
        "sha256:session",
        str(transcript),
        source_basename="session",
        source_path=str(transcript),
    )
    from transcriptx.core.utils.processing_state import (
        load_processing_state,
        save_processing_state,
    )

    state = load_processing_state(validate=False)
    state["processed_files"]["abc"] = {
        "transcript_path": str(transcript),
        "mp3_path": str(recording),
    }
    save_processing_state(state)

    result = delete_managed_library_transcript(transcript)
    assert result.ok
    assert result.transcript_deleted
    assert not transcript.exists()
    assert not sidecar.exists()
    assert not readable.exists()
    assert recording.exists()
    assert run_dir.exists()
    leftover = load_processing_state(validate=False)
    assert leftover.get("processed_files") == {}
    index = json.loads(transcript_roots["index"].read_text(encoding="utf-8"))
    assert "sha256:session" not in (index.get("transcripts") or {})


def test_delete_refuses_non_library_path(tmp_path: Path) -> None:
    outsider = tmp_path / "not-library.json"
    outsider.write_text("{}", encoding="utf-8")
    result = delete_managed_library_transcript(outsider)
    assert not result.ok
    assert outsider.exists()
    assert result.errors


def test_delete_does_not_surface_unrelated_group_manifest_warnings(
    transcript_roots, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pre-existing broken group manifests must not flood Library delete feedback."""
    import transcriptx.core.store.group_manifest_store as group_store_module
    from transcriptx.core.store.group_manifest_store import GroupManifestStore

    transcripts = transcript_roots["transcripts"]
    groups_dir = tmp_path / "groups"
    groups_dir.mkdir()
    monkeypatch.setattr(group_store_module, "_GROUPS_DIR", groups_dir, raising=False)
    monkeypatch.setattr(
        group_store_module,
        "_TRANSCRIPTS_DIR",
        transcripts,
        raising=False,
    )

    transcript_keep = transcripts / "keep.json"
    transcript_delete = transcripts / "delete.json"
    transcript_keep.write_text("{}", encoding="utf-8")
    transcript_delete.write_text("{}", encoding="utf-8")
    GroupManifestStore().create_group(
        name="Good",
        members=[transcript_keep],
    )
    bad_path = groups_dir / "deadbeef-dead-dead-dead-deadbeef0001.group.json"
    bad_path.write_text(
        json.dumps(
            {
                "version": 1,
                "group_id": "deadbeef-dead-dead-dead-deadbeef0001",
                "name": "Broken",
                "members": ["data/transcripts/a_group_test.json"],
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    result = delete_managed_library_transcript(transcript_delete)
    assert result.ok
    assert not transcript_delete.exists()
    assert transcript_keep.exists()
    assert not any("a_group_test" in warn for warn in result.warnings)
