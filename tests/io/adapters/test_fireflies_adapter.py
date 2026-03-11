"""Tests for FirefliesAdapter."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.io.adapters.fireflies_adapter import FirefliesAdapter
from transcriptx.io.intermediate_transcript import IntermediateTranscript

FIXTURES = (
    Path(__file__).parent.parent.parent / "fixtures" / "transcripts" / "fireflies"
)


class TestFirefliesAdapterDetect:
    def test_confident_on_fireflies_json(self):
        adapter = FirefliesAdapter()
        path = FIXTURES / "sample.json"
        assert adapter.detect_confidence(path, path.read_bytes()[:4096]) >= 0.8

    def test_zero_on_whisperx(self):
        adapter = FirefliesAdapter()
        data = {"segments": [{"start": 0.0, "end": 1.0, "text": "Hi", "speaker": "S0"}]}
        assert (
            adapter.detect_confidence(Path("t.json"), json.dumps(data).encode()) == 0.0
        )

    def test_zero_on_otter(self):
        adapter = FirefliesAdapter()
        data = {
            "speech_segments": [{"transcript": "Hi", "start_ts": 0.0, "end_ts": 1.0}]
        }
        assert (
            adapter.detect_confidence(Path("t.json"), json.dumps(data).encode()) == 0.0
        )


class TestFirefliesAdapterParse:
    def test_parses_fixture(self):
        adapter = FirefliesAdapter()
        path = FIXTURES / "sample.json"
        result = adapter.parse(path, path.read_bytes())

        assert isinstance(result, IntermediateTranscript)
        assert result.source_tool == "fireflies"
        assert len(result.turns) == 3
        assert not result.warnings

    def test_speaker_names(self):
        adapter = FirefliesAdapter()
        path = FIXTURES / "sample.json"
        result = adapter.parse(path, path.read_bytes())

        speakers = [t.speaker for t in result.turns]
        assert "Alice" in speakers
        assert "Bob" in speakers

    def test_timestamps(self):
        adapter = FirefliesAdapter()
        path = FIXTURES / "sample.json"
        result = adapter.parse(path, path.read_bytes())

        for turn in result.turns:
            assert turn.start is not None
            assert turn.end is not None

    def test_preamble_discarded(self):
        """meeting.summary should not appear as a turn."""
        adapter = FirefliesAdapter()
        path = FIXTURES / "sample.json"
        result = adapter.parse(path, path.read_bytes())

        all_text = " ".join(t.text for t in result.turns)
        assert "covering feature roadmap" not in all_text

    def test_raw_turn_id_from_index(self):
        adapter = FirefliesAdapter()
        path = FIXTURES / "sample.json"
        result = adapter.parse(path, path.read_bytes())

        assert result.turns[0].raw_turn_id == "0"
        assert result.turns[1].raw_turn_id == "1"
