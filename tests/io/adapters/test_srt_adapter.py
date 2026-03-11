"""
Tests for SRTAdapter.
"""
from __future__ import annotations

from pathlib import Path

from transcriptx.io.adapters.srt_adapter import SRTAdapter
from transcriptx.io.intermediate_transcript import IntermediateTranscript

FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "srt"


class TestSRTAdapterDetect:
    def test_confident_on_srt_content(self):
        adapter = SRTAdapter()
        content = b"1\n00:00:01,000 --> 00:00:02,000\nHi there\n\n"
        assert adapter.detect_confidence(Path("test.srt"), content) >= 0.9

    def test_zero_on_vtt(self):
        adapter = SRTAdapter()
        content = b"WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHi\n"
        assert adapter.detect_confidence(Path("test.srt"), content) == 0.0

    def test_zero_on_json(self):
        adapter = SRTAdapter()
        content = b'{"segments": []}'
        assert adapter.detect_confidence(Path("test.srt"), content) == 0.0


class TestSRTAdapterParse:
    def test_parses_simple_srt(self):
        adapter = SRTAdapter()
        path = FIXTURES / "simple.srt"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        assert isinstance(result, IntermediateTranscript)
        assert result.source_tool == "srt"
        assert result.source_format == "srt"
        assert len(result.turns) > 0
        assert not result.warnings

    def test_turns_have_timestamps(self):
        adapter = SRTAdapter()
        path = FIXTURES / "simple.srt"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        for turn in result.turns:
            assert turn.start is not None
            assert turn.end is not None
            assert turn.end > turn.start

    def test_turn_index_sequential(self):
        adapter = SRTAdapter()
        path = FIXTURES / "simple.srt"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        for i, turn in enumerate(result.turns):
            assert turn.turn_index == i

    def test_words_field_is_none(self):
        adapter = SRTAdapter()
        path = FIXTURES / "simple.srt"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        for turn in result.turns:
            assert turn.words is None
