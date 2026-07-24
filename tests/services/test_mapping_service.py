"""Unit tests for SpeakerMappingService."""

from __future__ import annotations

import json


from transcriptx.services.speaker_studio import SpeakerMappingService
from transcriptx.io.speaker_map_resolver import SpeakerMapResolver, sidecar_path_for


def test_assign_speaker(tmp_path) -> None:
    path = tmp_path / "t.json"
    original = {"segments": [{"speaker": "SPEAKER_00", "text": "Hi"}]}
    path.write_text(json.dumps(original))
    svc = SpeakerMappingService()
    state = svc.assign_speaker(str(path), "SPEAKER_00", "Alice", method="web")
    assert state.speaker_map.get("SPEAKER_00") == "Alice"
    assert state.schema_version == "1"
    assert state.provenance is not None
    assert state.provenance.get("method") == "web"
    assert json.loads(path.read_text()) == original
    assert SpeakerMapResolver().load_mapping(path).speaker_map == {
        "SPEAKER_00": "Alice"
    }
    assert sidecar_path_for(path).exists()


def test_ignore_speaker(tmp_path) -> None:
    path = tmp_path / "t.json"
    path.write_text(json.dumps({"segments": []}))
    svc = SpeakerMappingService()
    svc.ignore_speaker(str(path), "SPEAKER_01", method="web")
    state = svc.get_mapping(str(path))
    assert "SPEAKER_01" in state.ignored_speakers


def test_unignore_speaker(tmp_path) -> None:
    path = tmp_path / "t.json"
    path.write_text(json.dumps({"segments": []}))
    svc = SpeakerMappingService()
    svc.ignore_speaker(str(path), "SPEAKER_01", method="web")
    svc.unignore_speaker(str(path), "SPEAKER_01", method="web")
    state = svc.get_mapping(str(path))
    assert "SPEAKER_01" not in state.ignored_speakers


def test_unignore_speaker_idempotent_when_not_ignored(tmp_path) -> None:
    """unignore_speaker on an ID that is not ignored should not raise and leave the list unchanged."""
    path = tmp_path / "t.json"
    path.write_text(json.dumps({"segments": []}))
    svc = SpeakerMappingService()
    state = svc.unignore_speaker(str(path), "SPEAKER_99", method="web")
    assert "SPEAKER_99" not in state.ignored_speakers


def test_bulk_update(tmp_path) -> None:
    path = tmp_path / "t.json"
    payload = {
        "segments": [
            {"speaker": "SPEAKER_00", "text": "A"},
            {"speaker": "SPEAKER_01", "text": "B"},
        ]
    }
    path.write_text(json.dumps(payload))
    svc = SpeakerMappingService()
    svc.bulk_update(
        str(path), {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"}, [], method="batch"
    )
    data = json.loads(path.read_text())
    assert data == payload
    sidecar = SpeakerMapResolver().load_mapping(path)
    assert sidecar.speaker_map == {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"}
    assert sidecar.has_sidecar is True
