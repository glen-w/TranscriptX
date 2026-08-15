"""Tests for deleting transcripts linked to merge source audio."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.core.audio.linked_transcripts import (
    companion_files_for_transcript,
    delete_linked_transcripts_for_audio,
    find_transcripts_for_audio,
)


@pytest.fixture
def transcript_roots(tmp_path: Path, monkeypatch):
    transcripts = tmp_path / "transcripts"
    metadata = transcripts / "metadata"
    speaker_maps = metadata / "speaker_maps"
    readable = transcripts / "readable"
    originals = transcripts / "originals"
    for path in (transcripts, metadata, speaker_maps, readable, originals):
        path.mkdir(parents=True)

    import transcriptx.core.audio.linked_transcripts as linked
    import transcriptx.io.import_metadata.paths as import_paths

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
    return {
        "transcripts": transcripts,
        "readable": readable,
        "originals": originals,
        "state_file": state_file,
    }


def test_finds_same_stem_transcript(transcript_roots, tmp_path: Path) -> None:
    audio = tmp_path / "20260623204820-01.mp3"
    audio.write_bytes(b"a")
    transcript = transcript_roots["transcripts"] / "20260623204820-01.json"
    transcript.write_text("{}", encoding="utf-8")
    other = transcript_roots["transcripts"] / "20260623204820-02.json"
    other.write_text("{}", encoding="utf-8")

    found = find_transcripts_for_audio(audio)
    assert [p.name for p in found] == ["20260623204820-01.json"]


def test_finds_processing_state_link(transcript_roots, tmp_path: Path) -> None:
    audio = tmp_path / "part.wav"
    audio.write_bytes(b"a")
    transcript = transcript_roots["transcripts"] / "renamed_part.json"
    transcript.write_text("{}", encoding="utf-8")
    from transcriptx.core.utils.processing_state import (
        load_processing_state,
        save_processing_state,
    )

    state = load_processing_state(validate=False)
    state["processed_files"]["abc"] = {
        "transcript_path": str(transcript),
        "audio_path": str(audio),
    }
    save_processing_state(state)

    found = find_transcripts_for_audio(audio)
    assert found == [transcript]


def test_delete_removes_transcript_sidecar_and_state(
    transcript_roots, tmp_path: Path
) -> None:
    audio = tmp_path / "part.mp3"
    audio.write_bytes(b"a")
    transcript = transcript_roots["transcripts"] / "part.json"
    transcript.write_text("{}", encoding="utf-8")
    sidecar = transcript.with_name("part.speaker_map.json")
    sidecar.write_text("{}", encoding="utf-8")
    readable = transcript_roots["readable"] / "part.txt"
    readable.write_text("hello", encoding="utf-8")
    from transcriptx.core.utils.processing_state import (
        load_processing_state,
        save_processing_state,
    )

    state = load_processing_state(validate=False)
    state["processed_files"]["abc"] = {
        "transcript_path": str(transcript),
        "mp3_path": str(audio),
    }
    save_processing_state(state)

    companions = companion_files_for_transcript(transcript)
    assert transcript in companions
    assert sidecar in companions

    deleted, warnings = delete_linked_transcripts_for_audio(audio)
    assert deleted == 1
    assert warnings == []
    assert not transcript.exists()
    assert not sidecar.exists()
    assert not readable.exists()
    leftover = load_processing_state(validate=False)
    assert leftover.get("processed_files") == {}


def test_delete_leaves_unrelated_transcript(transcript_roots, tmp_path: Path) -> None:
    audio = tmp_path / "part_01.mp3"
    audio.write_bytes(b"a")
    keep = transcript_roots["transcripts"] / "part_02.json"
    keep.write_text("{}", encoding="utf-8")
    delete_linked_transcripts_for_audio(audio)
    assert keep.exists()
