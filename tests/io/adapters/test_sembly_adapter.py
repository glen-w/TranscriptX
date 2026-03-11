"""
Tests for SemblyAdapter (JSON and HTML).
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from transcriptx.io.adapters.sembly_adapter import SemblyAdapter
from transcriptx.io.intermediate_transcript import IntermediateTranscript

FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "transcripts" / "sembly"


class TestSemblyAdapterDetectJSON:
    def test_confident_on_sembly_json(self):
        adapter = SemblyAdapter()
        path = FIXTURES / "sample.json"
        content = path.read_bytes()
        score = adapter.detect_confidence(path, content[:4096])
        assert score >= 0.8

    def test_zero_on_whisperx_json(self):
        adapter = SemblyAdapter()
        data = {"segments": [{"start": 0.0, "end": 1.0, "text": "Hi", "speaker": "SPEAKER_00"}]}
        content = json.dumps(data).encode()
        assert adapter.detect_confidence(Path("test.json"), content) == 0.0

    def test_zero_on_empty_json(self):
        adapter = SemblyAdapter()
        content = b"{}"
        assert adapter.detect_confidence(Path("test.json"), content) == 0.0


class TestSemblyAdapterDetectHTML:
    def test_confident_on_sembly_html(self):
        adapter = SemblyAdapter()
        path = FIXTURES / "sample.html"
        content = path.read_bytes()
        score = adapter.detect_confidence(path, content[:4096])
        assert score >= 0.8

    def test_zero_on_non_sembly_html(self):
        adapter = SemblyAdapter()
        content = b"<html><body><p>Hello world</p></body></html>"
        assert adapter.detect_confidence(Path("test.html"), content) == 0.0


class TestSemblyAdapterParseJSON:
    def test_produces_intermediate_transcript(self):
        adapter = SemblyAdapter()
        path = FIXTURES / "sample.json"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        assert isinstance(result, IntermediateTranscript)
        assert result.source_tool == "sembly"
        assert result.source_format == "json"
        assert len(result.turns) == 3
        assert not result.warnings

    def test_speaker_names_preserved(self):
        adapter = SemblyAdapter()
        path = FIXTURES / "sample.json"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        speakers = [t.speaker for t in result.turns]
        assert "Alice Smith" in speakers
        assert "Bob Jones" in speakers

    def test_timestamps_parsed(self):
        adapter = SemblyAdapter()
        path = FIXTURES / "sample.json"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        for turn in result.turns:
            assert turn.start is not None
            assert turn.end is not None
            assert turn.end > turn.start

    def test_raw_turn_id_from_id_field(self):
        adapter = SemblyAdapter()
        path = FIXTURES / "sample.json"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        assert result.turns[0].raw_turn_id == "t1"
        assert result.turns[1].raw_turn_id == "t2"

    def test_adapter_discards_summary_and_action_items(self):
        """Adapter should strip preamble (summary, action_items) from turns."""
        adapter = SemblyAdapter()
        path = FIXTURES / "sample.json"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        # No "summary" or "action_items" text should appear in turns
        all_text = " ".join(t.text for t in result.turns)
        assert "kick off the project" not in all_text  # from summary
        assert "Send the agenda" not in all_text  # from action_items

    def test_source_metadata_has_participants(self):
        adapter = SemblyAdapter()
        path = FIXTURES / "sample.json"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        assert "participants" in result.source_metadata


class TestSemblyAdapterParseHTML:
    def test_produces_intermediate_transcript(self):
        adapter = SemblyAdapter()
        path = FIXTURES / "sample.html"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        assert isinstance(result, IntermediateTranscript)
        assert result.source_tool == "sembly"
        assert result.source_format == "html"
        assert len(result.turns) == 3

    def test_speaker_names_from_html(self):
        adapter = SemblyAdapter()
        path = FIXTURES / "sample.html"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        speakers = [t.speaker for t in result.turns]
        assert "Alice Smith" in speakers
        assert "Bob Jones" in speakers

    def test_timestamps_from_data_attributes(self):
        adapter = SemblyAdapter()
        path = FIXTURES / "sample.html"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        assert result.turns[0].start == pytest.approx(0.0)
        assert result.turns[0].end == pytest.approx(4.2)
        assert result.turns[1].start == pytest.approx(4.5)

    def test_html_preamble_discarded(self):
        """HTML adapter should only extract .transcript-item blocks."""
        adapter = SemblyAdapter()
        path = FIXTURES / "sample.html"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        # "summary" text should not appear in turns
        all_text = " ".join(t.text for t in result.turns)
        assert "kick off the project" not in all_text
        assert "Send the agenda" not in all_text

    def test_json_and_html_produce_equivalent_turns(self):
        """Both Sembly export formats should produce semantically equivalent output."""
        adapter = SemblyAdapter()

        json_result = adapter.parse(
            FIXTURES / "sample.json", (FIXTURES / "sample.json").read_bytes()
        )
        html_result = adapter.parse(
            FIXTURES / "sample.html", (FIXTURES / "sample.html").read_bytes()
        )

        assert len(json_result.turns) == len(html_result.turns)
        for j, h in zip(json_result.turns, html_result.turns):
            assert j.speaker == h.speaker
            assert j.start == pytest.approx(h.start, abs=0.01)
            assert j.end == pytest.approx(h.end, abs=0.01)
            assert j.text == h.text


class TestSemblyIntegration:
    """Integration test: Sembly fixture → JSON artifact → load_segments roundtrip."""

    def test_sembly_json_to_artifact_roundtrip(self):
        from transcriptx.io.transcript_normalizer import TranscriptNormalizer
        from transcriptx.io.speaker_normalizer import normalize_speakers
        from transcriptx.io.transcript_schema import (
            SourceInfo, create_transcript_document, validate_transcript_document
        )
        from datetime import datetime

        adapter = SemblyAdapter()
        path = FIXTURES / "sample.json"
        content = path.read_bytes()

        intermediate = adapter.parse(path, content)
        turns = TranscriptNormalizer().normalize(intermediate)
        segments = normalize_speakers(turns)

        source_info = SourceInfo(
            type=adapter.source_id,
            original_path=str(path),
            imported_at=datetime.utcnow().isoformat() + "Z",
        )
        document = create_transcript_document(segments, source_info)
        validate_transcript_document(document)

        assert document["source"]["type"] == "sembly"
        assert len(document["segments"]) == 3
        for seg in document["segments"]:
            assert seg["start"] >= 0
            assert seg["end"] > seg["start"]
            assert seg["text"]
            assert seg["speaker"] is not None
