"""Tests for OtterAdapter."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.io.adapters.otter_adapter import OtterAdapter
from transcriptx.io.intermediate_transcript import IntermediateTranscript

FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "transcripts" / "otter"


class TestOtterAdapterDetect:
    def test_confident_on_otter_json(self):
        adapter = OtterAdapter()
        path = FIXTURES / "sample.json"
        assert adapter.detect_confidence(path, path.read_bytes()[:4096]) >= 0.8

    def test_zero_on_whisperx(self):
        adapter = OtterAdapter()
        data = {"segments": [{"start": 0.0, "end": 1.0, "text": "Hi", "speaker": "S0"}]}
        assert (
            adapter.detect_confidence(Path("t.json"), json.dumps(data).encode()) == 0.0
        )

    def test_zero_on_sembly(self):
        adapter = OtterAdapter()
        data = {
            "transcript": [
                {
                    "speaker_name": "Alice",
                    "start_time": 0.0,
                    "end_time": 2.0,
                    "words_str": "Hi",
                }
            ],
            "participants": [],
        }
        assert (
            adapter.detect_confidence(Path("t.json"), json.dumps(data).encode()) == 0.0
        )


class TestOtterAdapterParse:
    def test_parses_fixture(self):
        adapter = OtterAdapter()
        path = FIXTURES / "sample.json"
        result = adapter.parse(path, path.read_bytes())

        assert isinstance(result, IntermediateTranscript)
        assert result.source_tool == "otter"
        assert len(result.turns) == 3
        assert not result.warnings

    def test_speaker_names(self):
        adapter = OtterAdapter()
        path = FIXTURES / "sample.json"
        result = adapter.parse(path, path.read_bytes())

        speakers = [t.speaker for t in result.turns]
        assert "Alice" in speakers
        assert "Bob" in speakers

    def test_timestamps(self):
        adapter = OtterAdapter()
        path = FIXTURES / "sample.json"
        result = adapter.parse(path, path.read_bytes())

        for turn in result.turns:
            assert turn.start is not None
            assert turn.end is not None

    def test_preamble_discarded(self):
        """summary and title should not appear as turns."""
        adapter = OtterAdapter()
        path = FIXTURES / "sample.json"
        result = adapter.parse(path, path.read_bytes())

        all_text = " ".join(t.text for t in result.turns)
        assert "action_items" not in all_text.lower()
        assert "planning" not in all_text.lower() or "Q1 planning" in all_text
