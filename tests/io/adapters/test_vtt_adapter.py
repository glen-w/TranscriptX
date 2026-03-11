"""
Tests for VTTAdapter.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.io.adapters.vtt_adapter import VTTAdapter
from transcriptx.io.intermediate_transcript import IntermediateTranscript, IntermediateTurn

FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "vtt"


class TestVTTAdapterDetect:
    def test_confident_on_webvtt_header(self):
        adapter = VTTAdapter()
        content = b"WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHi\n"
        assert adapter.detect_confidence(Path("test.vtt"), content) == 1.0

    def test_confident_with_bom(self):
        adapter = VTTAdapter()
        content = b"\xef\xbb\xbfWEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHi\n"
        assert adapter.detect_confidence(Path("test.vtt"), content) == 1.0

    def test_zero_on_non_vtt(self):
        adapter = VTTAdapter()
        content = b'{"segments": []}'
        assert adapter.detect_confidence(Path("test.vtt"), content) == 0.0


class TestVTTAdapterParse:
    def test_parses_simple_vtt(self):
        adapter = VTTAdapter()
        path = FIXTURES / "simple.vtt"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        assert isinstance(result, IntermediateTranscript)
        assert result.source_tool == "vtt"
        assert result.source_format == "vtt"
        assert len(result.turns) == 3
        assert not result.warnings

    def test_turns_have_timestamps(self):
        adapter = VTTAdapter()
        path = FIXTURES / "simple.vtt"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        for turn in result.turns:
            assert turn.start is not None
            assert turn.end is not None
            assert turn.end > turn.start

    def test_parses_speaker_hints(self):
        adapter = VTTAdapter()
        path = FIXTURES / "with_speakers.vtt"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        speakers = [t.speaker for t in result.turns]
        assert any(s is not None for s in speakers)

    def test_turn_index_sequential(self):
        adapter = VTTAdapter()
        path = FIXTURES / "simple.vtt"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        for i, turn in enumerate(result.turns):
            assert turn.turn_index == i

    def test_raw_turn_id_from_cue_ids(self):
        adapter = VTTAdapter()
        path = FIXTURES / "with_cue_ids.vtt"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        assert result.turns[0].raw_turn_id == "cue-1"
        assert result.turns[1].raw_turn_id == "cue-2"

    def test_no_speaker_hints_yields_none(self):
        adapter = VTTAdapter()
        path = FIXTURES / "simple.vtt"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        for turn in result.turns:
            assert turn.speaker is None

    def test_words_field_is_none(self):
        adapter = VTTAdapter()
        path = FIXTURES / "simple.vtt"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        for turn in result.turns:
            assert turn.words is None
