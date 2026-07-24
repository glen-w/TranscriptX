"""Tests for speaker map resolver."""

from __future__ import annotations

import json

import pytest

from transcriptx.io.speaker_map_resolver import (
    SpeakerMapResolver,
    sidecar_path_for,
    speaker_map_sidecar_candidates,
)


def test_sidecar_path_for_uses_same_stem(tmp_path) -> None:
    transcript = tmp_path / "folder" / "meeting.json"
    transcript.parent.mkdir(parents=True)

    assert sidecar_path_for(transcript) == transcript.with_name(
        "meeting.speaker_map.json"
    )


def test_missing_sidecar_returns_empty_state(tmp_path) -> None:
    transcript = tmp_path / "meeting.json"
    transcript.write_text(json.dumps({"segments": []}))

    state = SpeakerMapResolver().load_mapping(transcript)

    assert state.has_sidecar is False
    assert state.speaker_map == {}
    assert state.ignored_speakers == []
    assert state.is_unmapped is True
    assert state.has_named_speakers is False
    assert state.named_speaker_count == 0
    assert state.ignored_speaker_count == 0


def test_loads_sidecar_and_computes_properties(tmp_path) -> None:
    transcript = tmp_path / "meeting.json"
    transcript.write_text(json.dumps({"segments": []}))
    sidecar = sidecar_path_for(transcript)
    sidecar.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "speaker_map": {
                    "SPEAKER_00": "Alice",
                    "SPEAKER_01": "",
                    "SPEAKER_02": "Bob",
                },
                "ignored_speakers": ["SPEAKER_02", "SPEAKER_99"],
                "speaker_id_to_db_id": {"SPEAKER_00": 1},
                "speaker_map_provenance": {"method": "web"},
            }
        )
    )

    state = SpeakerMapResolver().load_mapping(transcript)

    assert state.has_sidecar is True
    assert state.schema_version == "1"
    assert state.provenance == {"method": "web"}
    assert state.speaker_map["SPEAKER_00"] == "Alice"
    assert state.speaker_map["SPEAKER_01"] == ""
    assert state.speaker_id_to_db_id == {"SPEAKER_00": 1}
    assert state.ignored_speakers == ["SPEAKER_02", "SPEAKER_99"]
    assert state.ignored_speaker_count == 2
    assert state.named_speaker_count == 1
    assert state.has_named_speakers is True
    assert state.is_unmapped is False


def test_malformed_sidecar_raises(tmp_path) -> None:
    transcript = tmp_path / "meeting.json"
    transcript.write_text(json.dumps({"segments": []}))
    sidecar = sidecar_path_for(transcript)
    sidecar.write_text("{not-json")

    with pytest.raises(ValueError):
        SpeakerMapResolver().load_mapping(transcript)


def test_resolve_segments_returns_new_list(tmp_path) -> None:
    transcript = tmp_path / "meeting.json"
    transcript.write_text(json.dumps({"segments": []}))
    sidecar = sidecar_path_for(transcript)
    sidecar.write_text(
        json.dumps(
            {
                "speaker_map": {"SPEAKER_00": "Alice"},
                "ignored_speakers": [],
            }
        )
    )

    resolver = SpeakerMapResolver()
    state = resolver.load_mapping(transcript)
    segments = [{"speaker": "SPEAKER_00", "text": "Hello"}]

    resolved = resolver.resolve_segments(segments, state)

    assert resolved is not segments
    assert resolved[0] is not segments[0]
    assert resolved[0]["speaker"] == "Alice"
    assert segments[0]["speaker"] == "SPEAKER_00"


def test_load_mapping_finds_sidecar_without_transcriptx_suffix(tmp_path) -> None:
    """Map file named {base}.speaker_map.json beside *_transcriptx.json transcript."""
    transcript = tmp_path / "meeting_transcriptx.json"
    transcript.write_text(json.dumps({"segments": []}))
    alt = tmp_path / "meeting.speaker_map.json"
    alt.write_text(
        json.dumps(
            {
                "speaker_map": {"SPEAKER_00": "Alice"},
                "ignored_speakers": [],
            }
        )
    )

    state = SpeakerMapResolver().load_mapping(transcript)

    assert state.has_sidecar is True
    assert state.speaker_map["SPEAKER_00"] == "Alice"


def test_speaker_map_sidecar_candidates_order(tmp_path) -> None:
    t = tmp_path / "a_transcriptx.json"
    c = speaker_map_sidecar_candidates(t)
    assert c[0].name == "a_transcriptx.speaker_map.json"
    assert c[1].name == "a.speaker_map.json"


def test_has_named_speakers_convenience_method(tmp_path) -> None:
    transcript = tmp_path / "meeting.json"
    transcript.write_text(json.dumps({"segments": []}))
    sidecar = sidecar_path_for(transcript)
    sidecar.write_text(
        json.dumps({"speaker_map": {"SPEAKER_00": "Alice"}, "ignored_speakers": []})
    )

    assert SpeakerMapResolver().has_named_speakers(transcript) is True


def test_load_mapping_with_sidecar_sets_named_speaker_count(tmp_path) -> None:
    """End-to-end: sidecar with two named speakers yields correct named_speaker_count."""
    transcript = tmp_path / "meeting.json"
    transcript.write_text(json.dumps({"segments": []}))
    sidecar = sidecar_path_for(transcript)
    sidecar.write_text(
        json.dumps(
            {
                "speaker_map": {
                    "SPEAKER_00": "Alice",
                    "speaker_1": "Bob",
                },
                "ignored_speakers": [],
            }
        )
    )

    state = SpeakerMapResolver().load_mapping(transcript)
    assert state.has_sidecar is True
    assert state.named_speaker_count == 2


def test_named_speaker_count_excludes_placeholder_self_mapping(tmp_path) -> None:
    transcript = tmp_path / "meeting.json"
    transcript.write_text(json.dumps({"segments": []}))
    sidecar = sidecar_path_for(transcript)
    sidecar.write_text(
        json.dumps(
            {
                "speaker_map": {
                    "SPEAKER_00": "SPEAKER_00",
                    "SPEAKER_01": "Alice",
                },
                "ignored_speakers": [],
            }
        )
    )

    state = SpeakerMapResolver().load_mapping(transcript)
    assert state.named_speaker_count == 1
