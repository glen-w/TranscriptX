"""Tests for ZoomAdapter."""
from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.io.adapters.zoom_adapter import ZoomAdapter
from transcriptx.io.adapters.vtt_adapter import VTTAdapter
from transcriptx.io.intermediate_transcript import IntermediateTranscript

FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "transcripts" / "zoom"
VTT_FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "vtt"


class TestZoomAdapterDetect:
    def test_confident_on_zoom_vtt(self):
        adapter = ZoomAdapter()
        path = FIXTURES / "sample.vtt"
        score = adapter.detect_confidence(path, path.read_bytes()[:4096])
        assert score == 1.0

    def test_lower_confidence_than_standard_vtt_for_standard_vtt(self):
        """Standard VTT should score lower for ZoomAdapter than for VTTAdapter."""
        zoom = ZoomAdapter()
        vtt = VTTAdapter()
        path = VTT_FIXTURES / "with_speakers.vtt"
        content = path.read_bytes()[:4096]

        zoom_score = zoom.detect_confidence(path, content)
        vtt_score = vtt.detect_confidence(path, content)

        # VTTAdapter should win decisively for standard VTT
        assert vtt_score > zoom_score or zoom_score < 0.5

    def test_zero_on_non_vtt(self):
        adapter = ZoomAdapter()
        content = b'{"segments": []}'
        assert adapter.detect_confidence(Path("test.json"), content) == 0.0

    def test_zero_on_non_webvtt(self):
        adapter = ZoomAdapter()
        content = b"1\n00:00:01,000 --> 00:00:02,000\nHello\n\n"
        assert adapter.detect_confidence(Path("test.vtt"), content) == 0.0


class TestZoomAdapterParse:
    def test_parses_zoom_fixture(self):
        adapter = ZoomAdapter()
        path = FIXTURES / "sample.vtt"
        result = adapter.parse(path, path.read_bytes())

        assert isinstance(result, IntermediateTranscript)
        assert result.source_tool == "zoom"
        assert result.source_format == "vtt"
        assert len(result.turns) == 3
        assert not result.warnings

    def test_speaker_from_first_text_line(self):
        """Zoom double-line: first line is speaker name."""
        adapter = ZoomAdapter()
        path = FIXTURES / "sample.vtt"
        result = adapter.parse(path, path.read_bytes())

        speakers = [t.speaker for t in result.turns]
        assert "Alice Smith" in speakers
        assert "Bob Jones" in speakers

    def test_utterance_from_second_text_line(self):
        adapter = ZoomAdapter()
        path = FIXTURES / "sample.vtt"
        result = adapter.parse(path, path.read_bytes())

        assert "Hello everyone" in result.turns[0].text
        assert "Alice Smith" not in result.turns[0].text

    def test_timestamps(self):
        adapter = ZoomAdapter()
        path = FIXTURES / "sample.vtt"
        result = adapter.parse(path, path.read_bytes())

        assert result.turns[0].start == pytest.approx(0.0, abs=0.01)
        assert result.turns[0].end == pytest.approx(4.2, abs=0.01)
        assert result.turns[1].start == pytest.approx(4.5, abs=0.01)

    def test_cue_ids_preserved(self):
        adapter = ZoomAdapter()
        path = FIXTURES / "sample.vtt"
        result = adapter.parse(path, path.read_bytes())

        assert result.turns[0].raw_turn_id == "1"
        assert result.turns[1].raw_turn_id == "2"


class TestZoomRegistrySelection:
    def test_registry_selects_zoom_for_zoom_vtt(self):
        """Global registry must select ZoomAdapter over VTTAdapter for Zoom VTT.

        ZoomAdapter (priority=8) has a lower number than VTTAdapter (priority=10),
        so when both score 1.0 on a Zoom file the ZoomAdapter wins the tie.
        """
        from transcriptx.io.adapters import registry

        path = FIXTURES / "sample.vtt"
        content = path.read_bytes()
        adapter = registry.detect(path, content)
        assert adapter.source_id == "zoom"
