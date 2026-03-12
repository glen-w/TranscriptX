"""
Tests for AdapterRegistry detection logic.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.io.adapters import AdapterRegistry
from transcriptx.io.adapters.base import UnsupportedFormatError
from transcriptx.io.adapters.vtt_adapter import VTTAdapter
from transcriptx.io.adapters.srt_adapter import SRTAdapter
from transcriptx.io.adapters.whisperx_adapter import WhisperXAdapter

FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "transcripts"
VTT_FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "vtt"
SRT_FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "srt"


def _build_registry() -> AdapterRegistry:
    reg = AdapterRegistry()
    reg.register(VTTAdapter())
    reg.register(SRTAdapter())
    reg.register(WhisperXAdapter())
    return reg


class TestRegistryDetection:
    def test_detects_vtt(self):
        reg = _build_registry()
        path = VTT_FIXTURES / "simple.vtt"
        content = path.read_bytes()
        adapter = reg.detect(path, content)
        assert adapter.source_id == "vtt"

    def test_detects_srt(self):
        reg = _build_registry()
        path = SRT_FIXTURES / "simple.srt"
        content = path.read_bytes()
        adapter = reg.detect(path, content)
        assert adapter.source_id == "srt"

    def test_detects_whisperx_standard(self):
        reg = _build_registry()
        path = FIXTURES / "whisperx" / "standard.json"
        content = path.read_bytes()
        adapter = reg.detect(path, content)
        assert adapter.source_id == "whisperx"

    def test_detects_whisperx_word_level(self):
        reg = _build_registry()
        path = FIXTURES / "whisperx" / "word_level.json"
        content = path.read_bytes()
        adapter = reg.detect(path, content)
        assert adapter.source_id == "whisperx"

    def test_detects_whisperx_bare_list(self):
        reg = _build_registry()
        path = FIXTURES / "whisperx" / "bare_list.json"
        content = path.read_bytes()
        adapter = reg.detect(path, content)
        assert adapter.source_id == "whisperx"

    def test_transcriptx_artifact_not_matched_by_whisperx(self):
        """Already-normalised schema v1.0 artifact should not be matched."""
        _build_registry()
        artifact = {
            "schema_version": "1.0",
            "source": {
                "type": "vtt",
                "original_path": "/tmp/x.vtt",
                "imported_at": "2025-01-01T00:00:00Z",
            },
            "segments": [
                {"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00", "text": "Hi"}
            ],
        }
        content = json.dumps(artifact).encode()
        path = Path("test.json")
        # WhisperXAdapter should return 0.0 confidence
        whisperx = WhisperXAdapter()
        assert whisperx.detect_confidence(path, content[:4096]) == 0.0

    def test_force_adapter_bypasses_detection(self):
        reg = _build_registry()
        path = Path("anything.unknown")
        content = b"some content"
        adapter = reg.detect(path, content, force_adapter="vtt")
        assert adapter.source_id == "vtt"

    def test_force_adapter_unknown_raises(self):
        reg = _build_registry()
        with pytest.raises(UnsupportedFormatError, match="no_such_adapter"):
            reg.detect(Path("x.vtt"), b"", force_adapter="no_such_adapter")

    def test_unsupported_raises(self):
        reg = _build_registry()
        path = Path("mystery.xyz")
        content = b"completely opaque binary \x00\x01\x02\x03"
        with pytest.raises(UnsupportedFormatError):
            reg.detect(path, content)

    def test_detect_all_scores_returns_all(self):
        reg = _build_registry()
        path = VTT_FIXTURES / "simple.vtt"
        content = path.read_bytes()
        scores = reg.detect_all_scores(path, content)
        source_ids = [a.source_id for a, _ in scores]
        assert "vtt" in source_ids
        assert "srt" in source_ids
        assert "whisperx" in source_ids


class TestPriorityTieBreaking:
    def test_lower_priority_wins_on_equal_score(self):
        """Two adapters with the same score: lower priority value should win."""

        class AlphaAdapter:
            source_id = "alpha"
            supported_extensions = (".txt",)
            priority = 10

            def detect_confidence(self, path, content):
                return 0.5

            def parse(self, path, content):
                pass

        class BetaAdapter:
            source_id = "beta"
            supported_extensions = (".txt",)
            priority = 20

            def detect_confidence(self, path, content):
                return 0.5

            def parse(self, path, content):
                pass

        reg = AdapterRegistry()
        reg.register(BetaAdapter())  # registered first but higher priority number
        reg.register(AlphaAdapter())
        adapter = reg.detect(Path("test.txt"), b"content")
        assert adapter.source_id == "alpha"
