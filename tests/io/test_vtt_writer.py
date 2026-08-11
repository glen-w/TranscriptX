"""Tests for WebVTT writer."""

from pathlib import Path

from transcriptx.io.vtt_parser import parse_vtt_file, parse_vtt_timestamp
from transcriptx.io.vtt_writer import (
    format_vtt_timestamp,
    segments_to_vtt_text,
    write_vtt_file,
)


def test_format_vtt_timestamp_round_trips_representative_values() -> None:
    values = [0.0, 5.5, 65.123, 3723.456]

    for value in values:
        formatted = format_vtt_timestamp(value)
        assert parse_vtt_timestamp(formatted) == value


def test_segments_to_vtt_text_uses_voice_tag_per_segment() -> None:
    segments = [
        {"speaker": "Alice", "text": "Hello", "start": 0.0, "end": 1.25},
        {"speaker": "Bob", "text": "World", "start": 1.25, "end": 2.5},
    ]

    vtt_text = segments_to_vtt_text(segments)

    assert vtt_text.startswith("WEBVTT\n\n")
    assert "00:00:00.000 --> 00:00:01.250\n<v Alice>Hello\n\n" in vtt_text
    assert "00:00:01.250 --> 00:00:02.500\n<v Bob>World\n\n" in vtt_text


def test_write_vtt_file_round_trips_speaker_hints(tmp_path: Path) -> None:
    segments = [
        {"speaker": "Alice", "text": "Hello", "start": 0.0, "end": 1.0},
        {"speaker": "Bob", "text": "Goodbye", "start": 1.0, "end": 2.0},
    ]
    path = tmp_path / "out.vtt"

    returned_path = write_vtt_file(segments, path)
    cues = parse_vtt_file(path)

    assert returned_path == str(path)
    assert [cue.speaker_hint for cue in cues] == ["Alice", "Bob"]
    assert [cue.text for cue in cues] == ["Hello", "Goodbye"]


def test_segments_to_vtt_text_omits_voice_tag_without_speaker() -> None:
    segments = [{"text": "Narration", "start": 0.0, "end": 1.0}]
    vtt_text = segments_to_vtt_text(segments)
    assert "<v " not in vtt_text
    assert "Narration" in vtt_text
