"""Tests for sidecar-backed speaker mapping operations."""

from __future__ import annotations

import json

import pytest

from transcriptx.io.speaker_map_resolver import SpeakerMapResolver, sidecar_path_for
from transcriptx.io.speaker_mapping import build_speaker_map
from transcriptx.io.speaker_mapping.utils import compute_speaker_stats_from_segments
from transcriptx.services.speaker_studio import SpeakerMappingService


def _write_raw_transcript(tmp_path, name="test.json"):
    transcript_path = tmp_path / name
    transcript_payload = {
        "segments": [
            {"speaker": "SPEAKER_00", "text": "Hello"},
            {"speaker": "SPEAKER_01", "text": "World"},
        ]
    }
    transcript_path.write_text(json.dumps(transcript_payload))
    return transcript_path, transcript_payload


def test_speaker_mapping_service_assign_writes_sidecar_only(tmp_path) -> None:
    transcript_path, transcript_payload = _write_raw_transcript(tmp_path)

    state = SpeakerMappingService().assign_speaker(
        str(transcript_path), "SPEAKER_00", "Alice", method="web"
    )

    assert state.speaker_map.get("SPEAKER_00") == "Alice"
    assert state.has_sidecar is True
    assert state.provenance is not None
    assert state.provenance.get("method") == "web"

    transcript = json.loads(transcript_path.read_text())
    assert transcript == transcript_payload

    sidecar = json.loads(sidecar_path_for(transcript_path).read_text())
    assert sidecar["speaker_map"] == {"SPEAKER_00": "Alice"}
    assert sidecar["ignored_speakers"] == []


def test_ignore_and_unignore_update_sidecar_only(tmp_path) -> None:
    transcript_path, transcript_payload = _write_raw_transcript(tmp_path)
    service = SpeakerMappingService()

    service.ignore_speaker(str(transcript_path), "SPEAKER_01", method="web")
    state = service.get_mapping(str(transcript_path))
    assert "SPEAKER_01" in state.ignored_speakers

    service.unignore_speaker(str(transcript_path), "SPEAKER_01", method="web")
    state = service.get_mapping(str(transcript_path))
    assert "SPEAKER_01" not in state.ignored_speakers

    transcript = json.loads(transcript_path.read_text())
    assert transcript == transcript_payload


def test_bulk_update_writes_sidecar_and_leaves_transcript_raw(tmp_path) -> None:
    transcript_path, transcript_payload = _write_raw_transcript(tmp_path)
    speaker_map = {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"}

    state = SpeakerMappingService().bulk_update(
        str(transcript_path),
        speaker_map,
        [],
        method="batch",
        speaker_id_to_db_id={"SPEAKER_00": 1, "SPEAKER_01": 2},
    )

    assert state.speaker_map == speaker_map
    assert state.named_speaker_count == 2

    transcript = json.loads(transcript_path.read_text())
    assert transcript == transcript_payload

    resolved = SpeakerMapResolver().resolve_segments(
        transcript_payload["segments"], state
    )
    assert resolved[0]["speaker"] == "Alice"
    assert resolved[0]["speaker_db_id"] == 1
    assert resolved[1]["speaker"] == "Bob"
    assert resolved[1]["speaker_db_id"] == 2


def test_build_speaker_map_batch_updates_sidecar(tmp_path) -> None:
    transcript_path, transcript_payload = _write_raw_transcript(tmp_path)

    segments = transcript_payload["segments"]
    result = build_speaker_map(
        segments, batch_mode=True, transcript_path=str(transcript_path)
    )

    assert result == {"SPEAKER_00": "Speaker 1", "SPEAKER_01": "Speaker 2"}

    transcript = json.loads(transcript_path.read_text())
    assert transcript == transcript_payload
    sidecar = json.loads(sidecar_path_for(transcript_path).read_text())
    assert sidecar["speaker_map"] == result


class TestComputeSpeakerStatsFromSegments:
    """Tests for compute_speaker_stats_from_segments (one-pass, no _extract_segment_times in loops)."""

    def test_timestamps_present(self) -> None:
        segments = [
            {"speaker": "A", "text": "x", "start": 0.0, "end": 10.0},
            {"speaker": "A", "text": "y", "start": 10.0, "end": 20.0},
            {"speaker": "B", "text": "z", "start": 20.0, "end": 30.0},
        ]
        stats = compute_speaker_stats_from_segments(segments)
        assert stats["A"]["segment_count"] == 2
        assert stats["A"]["total_duration"] == 20.0
        assert stats["A"]["percent"] == pytest.approx(200 / 3, rel=1e-5)
        assert stats["B"]["segment_count"] == 1
        assert stats["B"]["total_duration"] == 10.0
        assert stats["B"]["percent"] == pytest.approx(100 / 3, rel=1e-5)

    def test_timestamps_missing(self) -> None:
        segments = [
            {"speaker": "A", "text": "x"},
            {"speaker": "A", "text": "y"},
            {"speaker": "B", "text": "z"},
        ]
        stats = compute_speaker_stats_from_segments(segments)
        assert stats["A"]["segment_count"] == 2
        assert stats["A"]["total_duration"] == 0.0
        assert stats["A"]["percent"] == pytest.approx(200 / 3, rel=1e-5)
        assert stats["B"]["segment_count"] == 1
        assert stats["B"]["percent"] == pytest.approx(100 / 3, rel=1e-5)

    def test_one_segment_missing_end_ignored_for_duration_still_counts(self) -> None:
        segments = [
            {"speaker": "A", "text": "x", "start": 0.0, "end": 10.0},
            {"speaker": "A", "text": "y", "start": 10.0},
        ]
        stats = compute_speaker_stats_from_segments(segments)
        assert stats["A"]["segment_count"] == 2
        assert stats["A"]["total_duration"] == 10.0
        assert stats["A"]["percent"] == 100.0
