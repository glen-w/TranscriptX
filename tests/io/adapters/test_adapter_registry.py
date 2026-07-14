"""Tests for import_core registry selection and compatibility behavior."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from transcriptx.io.import_adapters.registry_builtins import build_default_registry
from transcriptx.io.import_core.contracts import (
    AdapterCapabilities,
    AdapterKind,
    DetectionClass,
    DetectionInput,
    DetectionOutcome,
    ParseInput,
)
from transcriptx.io.import_core.errors import (
    AmbiguousImportError,
    UnsupportedImportError,
)
from transcriptx.io.import_core.registry import ImportAdapterRegistry
from transcriptx.io.intermediate_transcript import IntermediateTranscript

FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "transcripts"
VTT_FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "vtt"
SRT_FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "srt"


def _build_registry() -> ImportAdapterRegistry:
    return build_default_registry()


class TestRegistryDetection:
    def test_detects_vtt(self):
        reg = _build_registry()
        path = VTT_FIXTURES / "simple.vtt"
        content = path.read_bytes()
        selected = reg.detect(path, content)
        assert selected.adapter.adapter_id in {"zoom", "vtt"}

    def test_detects_srt(self):
        reg = _build_registry()
        path = SRT_FIXTURES / "simple.srt"
        content = path.read_bytes()
        selected = reg.detect(path, content)
        assert selected.adapter.adapter_id == "srt"

    def test_detects_whisperx_standard(self):
        reg = _build_registry()
        path = FIXTURES / "whisperx" / "standard.json"
        content = path.read_bytes()
        selected = reg.detect(path, content)
        assert selected.adapter.adapter_id == "whisperx"

    def test_detects_whisperx_word_level(self):
        reg = _build_registry()
        path = FIXTURES / "whisperx" / "word_level.json"
        content = path.read_bytes()
        selected = reg.detect(path, content)
        assert selected.adapter.adapter_id == "whisperx"

    def test_detects_whisperx_bare_list(self):
        reg = _build_registry()
        path = FIXTURES / "whisperx" / "bare_list.json"
        content = path.read_bytes()
        selected = reg.detect(path, content)
        assert selected.adapter.adapter_id == "whisperx"

    def test_detects_whisperx_large_json_beyond_snippet_window(self):
        """WhisperX JSON larger than the registry snippet window is still detected.

        Regression test: ensure ImportAdapter.probe reads full content and
        does not rely solely on the truncated snippet, which can be invalid JSON
        for large WhisperX outputs.
        """
        reg = _build_registry()
        base_path = FIXTURES / "whisperx" / "standard.json"
        doc = json.loads(base_path.read_text(encoding="utf-8"))
        base_seg = doc["segments"][0]
        # Many segments in one object so the file exceeds the snippet window but stays valid JSON.
        doc["segments"] = [
            {
                **base_seg,
                "start": float(i),
                "end": float(i) + 0.5,
                "text": f"segment-{i}",
            }
            for i in range(400)
        ]
        large_payload = json.dumps(doc)

        tmp_path = FIXTURES / "whisperx" / "standard_large.json"
        tmp_path.write_text(large_payload, encoding="utf-8")
        try:
            content = tmp_path.read_bytes()
            selected = reg.detect(tmp_path, content)
            assert selected.adapter.adapter_id == "whisperx"
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_force_adapter_bypasses_detection(self):
        reg = _build_registry()
        path = Path("anything.unknown")
        content = b"some content"
        selected = reg.detect(path, content, force_adapter="vtt")
        assert selected.adapter.adapter_id == "vtt"

    def test_force_adapter_unknown_raises(self):
        reg = _build_registry()
        with pytest.raises(UnsupportedImportError):
            reg.detect(Path("x.vtt"), b"", force_adapter="no_such_adapter")

    def test_unsupported_raises(self):
        reg = _build_registry()
        path = Path("mystery.xyz")
        content = b"completely opaque binary \x00\x01\x02\x03"
        with pytest.raises(UnsupportedImportError):
            reg.detect(path, content)


class TestPriorityTieBreaking:
    def test_lower_priority_wins_on_equal_score(self):
        """Equal-score non-definitive matches are treated as ambiguous."""

        @dataclass
        class AlphaAdapter:
            adapter_id: str = "alpha"
            display_name: str = "alpha"
            adapter_kind: AdapterKind = AdapterKind.FAMILY
            supported_extensions = frozenset({".txt"})
            format_family: str = "plain_text"
            detection_priority: int = 10
            capabilities = AdapterCapabilities()

            def probe(self, input_data: DetectionInput):
                return DetectionOutcome(
                    detection_class=DetectionClass.LIKELY,
                    score=0.5,
                )

            def parse(self, input_data: ParseInput):
                return IntermediateTranscript(
                    source_tool="alpha",
                    source_format="txt",
                    turns=[],
                    source_metadata={},
                    warnings=[],
                )

        @dataclass
        class BetaAdapter:
            adapter_id: str = "beta"
            display_name: str = "beta"
            adapter_kind: AdapterKind = AdapterKind.FAMILY
            supported_extensions = frozenset({".txt"})
            format_family: str = "plain_text"
            detection_priority: int = 20
            capabilities = AdapterCapabilities()

            def probe(self, input_data: DetectionInput):
                return DetectionOutcome(
                    detection_class=DetectionClass.LIKELY,
                    score=0.5,
                )

            def parse(self, input_data: ParseInput):
                return IntermediateTranscript(
                    source_tool="beta",
                    source_format="txt",
                    turns=[],
                    source_metadata={},
                    warnings=[],
                )

        reg = ImportAdapterRegistry()
        reg.register(BetaAdapter())
        reg.register(AlphaAdapter())
        with pytest.raises(AmbiguousImportError):
            reg.detect(Path("test.txt"), b"content")
