"""Tests for srt writer."""

from pathlib import Path

from transcriptx.io.srt_parser import parse_srt_file, parse_srt_timestamp
from transcriptx.io.srt_writer import (
    format_srt_timestamp,
    segments_to_srt_text,
    write_srt_file,
)


def test_format_srt_timestamp_round_trips_representative_values() -> None:
    values = [0.0, 5.5, 65.123, 3723.456]

    for value in values:
        formatted = format_srt_timestamp(value)
        assert parse_srt_timestamp(formatted) == value


def test_segments_to_srt_text_uses_one_speaker_prefixed_cue_per_segment() -> None:
    segments = [
        {"speaker": "Alice", "text": "Hello", "start": 0.0, "end": 1.25},
        {"speaker": "Bob", "text": "World", "start": 1.25, "end": 2.5},
    ]

    srt_text = segments_to_srt_text(segments)

    assert "1\n00:00:00,000 --> 00:00:01,250\nAlice: Hello\n\n" in srt_text
    assert "2\n00:00:01,250 --> 00:00:02,500\nBob: World\n\n" in srt_text


def test_write_srt_file_round_trips_speaker_hints(tmp_path: Path) -> None:
    segments = [
        {"speaker": "Alice", "text": "Hello", "start": 0.0, "end": 1.0},
        {"speaker": "Bob", "text": "Goodbye", "start": 1.0, "end": 2.0},
    ]
    path = tmp_path / "out.srt"

    returned_path = write_srt_file(segments, path)
    cues = parse_srt_file(path)

    assert returned_path == str(path)
    assert [cue.speaker_hint for cue in cues] == ["Alice", "Bob"]
    assert [cue.text for cue in cues] == ["Hello", "Goodbye"]
