"""Tests for RevAdapter."""
from __future__ import annotations

import json
from pathlib import Path

from transcriptx.io.adapters.rev_adapter import RevAdapter
from transcriptx.io.intermediate_transcript import IntermediateTranscript

FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "transcripts" / "rev"


class TestRevAdapterDetect:
    def test_confident_on_rev_json(self):
        adapter = RevAdapter()
        path = FIXTURES / "sample.json"
        assert adapter.detect_confidence(path, path.read_bytes()[:4096]) >= 0.8

    def test_zero_on_whisperx(self):
        adapter = RevAdapter()
        data = {"segments": [{"start": 0.0, "end": 1.0, "text": "Hi", "speaker": "S0"}]}
        assert adapter.detect_confidence(Path("t.json"), json.dumps(data).encode()) == 0.0

    def test_zero_on_fireflies(self):
        adapter = RevAdapter()
        data = {"meeting": {"sentences": [{"text": "Hi", "start_time": 0.0, "end_time": 1.0}]}}
        assert adapter.detect_confidence(Path("t.json"), json.dumps(data).encode()) == 0.0


class TestRevAdapterParse:
    def test_parses_fixture(self):
        adapter = RevAdapter()
        path = FIXTURES / "sample.json"
        result = adapter.parse(path, path.read_bytes())

        assert isinstance(result, IntermediateTranscript)
        assert result.source_tool == "rev"
        assert len(result.turns) == 3
        assert not result.warnings

    def test_speaker_as_string_index(self):
        """Rev uses integer speaker IDs; adapter converts to string."""
        adapter = RevAdapter()
        path = FIXTURES / "sample.json"
        result = adapter.parse(path, path.read_bytes())

        speakers = [t.speaker for t in result.turns]
        assert "0" in speakers
        assert "1" in speakers

    def test_timestamps(self):
        adapter = RevAdapter()
        path = FIXTURES / "sample.json"
        result = adapter.parse(path, path.read_bytes())

        for turn in result.turns:
            assert turn.start is not None
            assert turn.end is not None

    def test_text_from_elements(self):
        """Text should be concatenated from elements of type 'text'."""
        adapter = RevAdapter()
        path = FIXTURES / "sample.json"
        result = adapter.parse(path, path.read_bytes())

        assert result.turns[0].text.strip() != ""
        assert "Hello" in result.turns[0].text
