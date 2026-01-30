"""
Tests for SRT parser.
"""

from pathlib import Path

from transcriptx.io.srt_parser import parse_srt_file, parse_srt_timestamp


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "srt"


def test_parse_srt_timestamp():
    assert parse_srt_timestamp("00:00:05,500") == 5.5
    assert parse_srt_timestamp("01:02:03,456") == 3723.456
    assert parse_srt_timestamp("00:05,500") == 5.5


def test_parse_srt_file_simple():
    srt_path = FIXTURES_DIR / "simple.srt"
    cues = parse_srt_file(srt_path)
    assert len(cues) == 3
    assert cues[0].start == 0.0
    assert cues[0].end == 3.4
    assert "Hello from speaker one." in cues[0].text
