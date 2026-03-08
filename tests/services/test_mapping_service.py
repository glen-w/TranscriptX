"""Unit tests for SpeakerMappingService."""

from __future__ import annotations

import json


from transcriptx.services.speaker_studio import SpeakerMappingService


def test_assign_speaker(tmp_path) -> None:
    path = tmp_path / "t.json"
    path.write_text(json.dumps({"segments": [{"speaker": "SPEAKER_00", "text": "Hi"}]}))
    svc = SpeakerMappingService()
    state = svc.assign_speaker(str(path), "SPEAKER_00", "Alice", method="web")
    assert state.speaker_map.get("SPEAKER_00") == "Alice"
    assert state.schema_version == "1.0"
    assert state.provenance is not None
    assert state.provenance.get("method") == "web"
    data = json.loads(path.read_text())
    assert data["segments"][0]["speaker"] == "Alice"


def test_ignore_speaker(tmp_path) -> None:
    path = tmp_path / "t.json"
    path.write_text(json.dumps({"segments": [], "speaker_map": {}}))
    svc = SpeakerMappingService()
    svc.ignore_speaker(str(path), "SPEAKER_01", method="web")
    state = svc.get_mapping(str(path))
    assert "SPEAKER_01" in state.ignored_speakers


def test_unignore_speaker(tmp_path) -> None:
    path = tmp_path / "t.json"
    path.write_text(json.dumps({"segments": [], "speaker_map": {}}))
    svc = SpeakerMappingService()
    svc.ignore_speaker(str(path), "SPEAKER_01", method="web")
    svc.unignore_speaker(str(path), "SPEAKER_01", method="web")
    state = svc.get_mapping(str(path))
    assert "SPEAKER_01" not in state.ignored_speakers


def test_unignore_speaker_idempotent_when_not_ignored(tmp_path) -> None:
    """unignore_speaker on an ID that is not ignored should not raise and leave the list unchanged."""
    path = tmp_path / "t.json"
    path.write_text(json.dumps({"segments": [], "speaker_map": {}}))
    svc = SpeakerMappingService()
    state = svc.unignore_speaker(str(path), "SPEAKER_99", method="web")
    assert "SPEAKER_99" not in state.ignored_speakers


def test_bulk_update(tmp_path) -> None:
    path = tmp_path / "t.json"
    path.write_text(
        json.dumps(
            {
                "segments": [
                    {"speaker": "SPEAKER_00", "text": "A"},
                    {"speaker": "SPEAKER_01", "text": "B"},
                ]
            }
        )
    )
    svc = SpeakerMappingService()
    svc.bulk_update(
        str(path), {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"}, [], method="batch"
    )
    data = json.loads(path.read_text())
    assert data["speaker_map"] == {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"}
    assert data["segments"][0]["speaker"] == "Alice"
    assert "speaker_map_provenance" in data
