"""
Tests for speaker mapping operations.

Speaker map sidecars have been removed. These tests validate:
- stub functions raise clear errors
- transcript JSON is updated by update_transcript_json_with_speaker_names()
- build_speaker_map(batch_mode=True) updates transcript JSON
"""

import json

import pytest

from transcriptx.io.speaker_mapping import build_speaker_map, load_speaker_map, save_speaker_map
from transcriptx.io.speaker_mapping.core import update_transcript_json_with_speaker_names


def test_save_speaker_map_stub_raises() -> None:
    with pytest.raises(RuntimeError, match="Speaker map sidecars removed"):
        save_speaker_map({})


def test_load_speaker_map_stub_raises() -> None:
    with pytest.raises(RuntimeError, match="Speaker map sidecars removed"):
        load_speaker_map("unused")


def test_update_transcript_json_with_speaker_names(tmp_path) -> None:
    transcript_path = tmp_path / "test.json"
    transcript_payload = {
        "segments": [
            {"speaker": "SPEAKER_00", "text": "Hello"},
            {"speaker": "SPEAKER_01", "text": "World"},
        ]
    }
    transcript_path.write_text(json.dumps(transcript_payload))

    speaker_map = {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"}
    speaker_db_ids = {"SPEAKER_00": 1, "SPEAKER_01": 2}

    update_transcript_json_with_speaker_names(
        str(transcript_path), speaker_map, speaker_db_ids
    )

    updated = json.loads(transcript_path.read_text())
    assert updated["segments"][0]["speaker"] == "Alice"
    assert updated["segments"][1]["speaker"] == "Bob"
    assert updated["segments"][0]["speaker_db_id"] == 1
    assert updated["segments"][1]["speaker_db_id"] == 2
    assert updated["speaker_map"] == speaker_map


def test_build_speaker_map_batch_updates_transcript(tmp_path) -> None:
    transcript_path = tmp_path / "test.json"
    transcript_payload = {
        "segments": [
            {"speaker": "SPEAKER_00", "text": "Hello"},
            {"speaker": "SPEAKER_01", "text": "World"},
        ]
    }
    transcript_path.write_text(json.dumps(transcript_payload))

    segments = transcript_payload["segments"]
    result = build_speaker_map(
        segments, batch_mode=True, transcript_path=str(transcript_path)
    )

    assert result == {"SPEAKER_00": "Speaker 1", "SPEAKER_01": "Speaker 2"}

    updated = json.loads(transcript_path.read_text())
    assert updated["segments"][0]["speaker"] == "Speaker 1"
    assert updated["segments"][1]["speaker"] == "Speaker 2"
    assert updated["speaker_map"] == result
